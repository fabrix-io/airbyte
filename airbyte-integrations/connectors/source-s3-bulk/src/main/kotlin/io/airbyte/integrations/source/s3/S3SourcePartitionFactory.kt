/* Copyright (c) 2024 Airbyte, Inc., all rights reserved. */
package io.airbyte.integrations.source.s3

import io.airbyte.cdk.read.*
import io.airbyte.cdk.command.SourceConfiguration
import io.airbyte.cdk.discover.Field
import io.github.oshai.kotlinlogging.KotlinLogging
import jakarta.inject.Inject
import jakarta.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import java.time.Instant

private val log = KotlinLogging.logger {}

@Singleton
class S3SourcePartitionFactory @Inject constructor(
    private val config: S3SourceConfiguration,
    private val s3ClientFactory: S3ClientFactory,
    private val selectQuerier: S3SourceSelectQuerier,
) : PartitionsCreatorFactory {
    
    override fun make(
        stateQuerier: StateQuerier,
        metaFieldDecorator: MetaFieldDecorator
    ): PartitionsCreator {
        return S3SourcePartitionsCreator(config, s3ClientFactory, selectQuerier, stateQuerier)
    }
}

class S3SourcePartitionsCreator(
    private val config: S3SourceConfiguration,
    private val s3ClientFactory: S3ClientFactory,
    private val selectQuerier: S3SourceSelectQuerier,
    private val stateQuerier: StateQuerier,
) : PartitionsCreator {
    
    override fun streamPartitions(
        stream: Stream,
        primaryKey: List<List<String>>?,
        cursorColumns: List<String>?,
    ): Flow<PartitionReadResult> = flow {
        log.info { "Creating partitions for stream: ${stream.id}" }
        
        val streamConfig = config.streams.find { it.name == stream.id.name }
            ?: throw IllegalArgumentException("Stream ${stream.id.name} not found in configuration")
        
        val s3Client = s3ClientFactory.createClient()
        val globs = streamConfig.globs ?: listOf(config.pathPattern)
        
        // Get the last sync state
        val streamState = stateQuerier.current(stream) as? S3StreamState
        val lastModifiedCutoff = streamState?.lastModified ?: config.startDate
        
        // List files and create partitions
        val files = s3Client.listFiles(config.bucketName, globs, lastModifiedCutoff)
            .sortedBy { it.lastModified }
            .toList()
        
        log.info { "Found ${files.size} files for stream ${stream.id.name}" }
        
        // Create a partition for each file
        files.forEach { file ->
            val partition = S3FilePartition(
                stream = stream,
                bucket = config.bucketName,
                key = file.key,
                size = file.size,
                lastModified = file.lastModified,
                streamConfig = streamConfig
            )
            
            val partitionReader = S3FilePartitionReader(
                partition = partition,
                selectQuerier = selectQuerier,
                stateQuerier = stateQuerier
            )
            
            emit(PartitionReadResult(partition, partitionReader))
        }
    }
}

/**
 * Represents a single S3 file as a partition
 */
data class S3FilePartition(
    val stream: Stream,
    val bucket: String,
    val key: String,
    val size: Long,
    val lastModified: Instant,
    val streamConfig: StreamConfiguration
) : Partition {
    override val completeState: OpaqueStateValue
        get() = S3StreamState(key = key, lastModified = lastModified)
    
    override val incompleteState: OpaqueStateValue
        get() = S3StreamState(key = key, lastModified = lastModified)
}

/**
 * State for tracking S3 stream progress
 */
data class S3StreamState(
    val key: String,
    val lastModified: Instant
) : OpaqueStateValue

/**
 * Partition reader for reading records from a single S3 file
 */
class S3FilePartitionReader(
    private val partition: S3FilePartition,
    private val selectQuerier: S3SourceSelectQuerier,
    private val stateQuerier: StateQuerier,
) : PartitionReader {
    
    override fun read(): Flow<PartitionRecord> = flow {
        log.info { "Reading partition for file: ${partition.key}" }
        
        // Create a select query for the file
        val selectQuery = SelectQuery(
            stream = partition.stream,
            bucket = partition.bucket,
            key = partition.key,
            format = partition.streamConfig.format,
            streamConfig = partition.streamConfig
        )
        
        // Read records from the file
        selectQuerier.select(selectQuery).collect { record ->
            emit(PartitionRecord(record.data, record.changes))
        }
    }
}
/* Copyright (c) 2024 Airbyte, Inc., all rights reserved. */
package io.airbyte.integrations.source.s3

import io.airbyte.cdk.command.SourceConfiguration
import io.airbyte.cdk.discover.AirbyteStreamFactory
import io.airbyte.cdk.discover.DiscoveredStream
import io.airbyte.cdk.discover.Field
import io.airbyte.cdk.discover.MetadataQuerier
import io.airbyte.cdk.discover.DiscoveredTableName
import io.airbyte.cdk.discover.StreamFieldStatistics
import io.airbyte.cdk.discover.StringFieldType
import io.airbyte.cdk.discover.DoubleFieldType
import io.airbyte.cdk.discover.IntegerFieldType
import io.airbyte.cdk.discover.BooleanFieldType
import io.airbyte.cdk.discover.ArrayFieldType
import io.airbyte.cdk.discover.ObjectFieldType
import io.airbyte.cdk.discover.UnknownFieldType
import io.airbyte.cdk.discover.FieldType
import io.airbyte.protocol.models.v0.AirbyteStream
import io.github.oshai.kotlinlogging.KotlinLogging
import io.micronaut.context.annotation.Secondary
import jakarta.inject.Inject
import jakarta.inject.Singleton
import java.util.concurrent.ConcurrentHashMap

private val log = KotlinLogging.logger {}

@Singleton
@Secondary
class S3SourceMetadataQuerier @Inject constructor(
    val config: S3SourceConfiguration,
    val s3ClientFactory: S3ClientFactory,
    val fileSchemaInferrer: FileSchemaInferrer,
) : MetadataQuerier {

    private val schemaCache = ConcurrentHashMap<String, List<Field>>()

    override fun streamNames(): List<DiscoveredTableName> {
        // Return stream names from configuration
        return config.streams.map { stream ->
            DiscoveredTableName(name = stream.name, namespace = null)
        }
    }

    override fun fields(streamName: String): List<Field> {
        log.info { "Discovering fields for stream: $streamName" }
        
        // Check cache first
        schemaCache[streamName]?.let { return it }
        
        val streamConfig = config.streams.find { it.name == streamName }
            ?: throw IllegalArgumentException("Stream $streamName not found in configuration")
        
        // If schema is provided in configuration, use it
        if (!streamConfig.inputSchema.isNullOrBlank()) {
            val fields = parseProvidedSchema(streamConfig.inputSchema)
            schemaCache[streamName] = fields
            return fields
        }
        
        // Otherwise, infer schema from files
        val inferredFields = inferSchemaFromFiles(streamConfig)
        schemaCache[streamName] = inferredFields
        return inferredFields
    }

    override fun streamFieldStatistics(streamName: String): List<StreamFieldStatistics> {
        // Return empty statistics for now - can be enhanced later
        return emptyList()
    }

    override fun close() {
        s3ClientFactory.close()
    }

    private fun parseProvidedSchema(schemaStr: String): List<Field> {
        // Parse JSON schema string to fields
        return fileSchemaInferrer.parseJsonSchema(schemaStr)
    }

    private fun inferSchemaFromFiles(streamConfig: StreamConfiguration): List<Field> {
        val s3Client = s3ClientFactory.createClient()
        val globs = streamConfig.globs ?: listOf(config.pathPattern)
        
        // List files matching the stream's glob patterns
        val matchingFiles = s3Client.listFiles(config.bucketName, globs, config.startDate)
            .take(10) // Sample up to 10 files for schema inference
            .toList()
        
        if (matchingFiles.isEmpty()) {
            log.warn { "No files found for stream ${streamConfig.name}, returning empty schema" }
            return emptyList()
        }
        
        // Infer schema based on file format
        return when (streamConfig.format) {
            is FileFormat.CsvFormat -> fileSchemaInferrer.inferCsvSchema(
                s3Client = s3Client,
                bucket = config.bucketName,
                files = matchingFiles,
                delimiter = streamConfig.delimiter,
                quoteChar = streamConfig.quoteChar,
                escapeChar = streamConfig.escapeChar,
                encoding = streamConfig.encoding,
                skipRowsBeforeHeader = streamConfig.skipRowsBeforeHeader,
                autogenerateColumnNames = streamConfig.autogenerateColumnNames,
                columnNames = streamConfig.columnNames
            )
            is FileFormat.ParquetFormat -> fileSchemaInferrer.inferParquetSchema(
                s3Client = s3Client,
                bucket = config.bucketName,
                files = matchingFiles
            )
            is FileFormat.AvroFormat -> fileSchemaInferrer.inferAvroSchema(
                s3Client = s3Client,
                bucket = config.bucketName,
                files = matchingFiles
            )
            is FileFormat.JsonlFormat -> fileSchemaInferrer.inferJsonlSchema(
                s3Client = s3Client,
                bucket = config.bucketName,
                files = matchingFiles
            )
        }
    }

    /**
     * Metadata querier factory.
     */
    @Singleton
    class Factory @Inject constructor(
        val config: S3SourceConfiguration,
        val s3ClientFactory: S3ClientFactory,
        val fileSchemaInferrer: FileSchemaInferrer,
    ) : MetadataQuerier.Factory<SourceConfiguration> {
        override fun session(config: SourceConfiguration): MetadataQuerier {
            return S3SourceMetadataQuerier(
                config = this.config,
                s3ClientFactory = s3ClientFactory,
                fileSchemaInferrer = fileSchemaInferrer,
            )
        }
    }
}

@Singleton
class S3SourceAirbyteStreamFactory : AirbyteStreamFactory {
    override fun create(config: SourceConfiguration, discoveredStream: DiscoveredStream): AirbyteStream {
        val s3Config = config as S3SourceConfiguration
        val stream = AirbyteStreamFactory.createAirbyteStream(discoveredStream)
        
        // Find stream configuration
        val streamConfig = s3Config.streams.find { it.name == discoveredStream.id.name }
        
        // Set primary key if specified
        streamConfig?.primaryKey?.let { pk ->
            stream.sourceDefinedPrimaryKey = listOf(listOf(pk))
        }
        
        return stream
    }
}
/* Copyright (c) 2024 Airbyte, Inc., all rights reserved. */
package io.airbyte.integrations.source.s3

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.databind.node.ObjectNode
import com.fasterxml.jackson.dataformat.csv.CsvMapper
import com.fasterxml.jackson.dataformat.csv.CsvParser
import com.fasterxml.jackson.dataformat.csv.CsvSchema
import io.airbyte.cdk.read.Stream
import io.airbyte.protocol.models.v0.AirbyteRecordMessageMeta
import io.github.oshai.kotlinlogging.KotlinLogging
import jakarta.inject.Inject
import jakarta.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import org.apache.avro.file.DataFileReader
import org.apache.avro.generic.GenericDatumReader
import org.apache.avro.generic.GenericRecord
import org.apache.parquet.avro.AvroParquetReader
import org.apache.parquet.hadoop.ParquetReader
import java.io.BufferedReader
import java.io.InputStreamReader
import java.nio.charset.Charset
import java.time.Instant

private val log = KotlinLogging.logger {}

@Singleton
class S3SourceSelectQuerier @Inject constructor(
    private val s3ClientFactory: S3ClientFactory,
    private val objectMapper: ObjectMapper
) {
    
    private val csvMapper = CsvMapper().apply {
        enable(CsvParser.Feature.WRAP_AS_ARRAY)
    }
    
    fun select(query: SelectQuery): Flow<S3Record> = flow {
        log.info { "Reading file ${query.key} with format ${query.format}" }
        
        val s3Client = s3ClientFactory.createClient()
        
        when (query.format) {
            is FileFormat.CsvFormat -> readCsv(s3Client, query)
            is FileFormat.ParquetFormat -> readParquet(s3Client, query)
            is FileFormat.AvroFormat -> readAvro(s3Client, query)
            is FileFormat.JsonlFormat -> readJsonl(s3Client, query)
        }.collect { record ->
            emit(record)
        }
    }
    
    private fun readCsv(s3Client: S3ClientWrapper, query: SelectQuery): Flow<S3Record> = flow {
        val inputStream = s3Client.getObjectInputStream(query.bucket, query.key)
        
        inputStream.use { stream ->
            val reader = BufferedReader(
                InputStreamReader(stream, Charset.forName(query.streamConfig.encoding))
            )
            
            // Skip rows before header
            repeat(query.streamConfig.skipRowsBeforeHeader) {
                reader.readLine()
            }
            
            // Get column names
            val headers = when {
                !query.streamConfig.columnNames.isNullOrEmpty() -> query.streamConfig.columnNames
                query.streamConfig.autogenerateColumnNames -> {
                    val firstLine = reader.readLine()
                    val numColumns = firstLine?.split(query.streamConfig.delimiter)?.size ?: 0
                    (1..numColumns).map { "column_$it" }
                }
                else -> {
                    val headerLine = reader.readLine()
                    headerLine?.split(query.streamConfig.delimiter)
                        ?.map { it.trim(query.streamConfig.quoteChar.first()) } ?: emptyList()
                }
            }
            
            // Skip rows after header
            repeat(query.streamConfig.skipRowsAfterHeader) {
                reader.readLine()
            }
            
            // Read data rows
            reader.lineSequence().forEach { line ->
                val values = parseCsvLine(line, query.streamConfig)
                if (values.size == headers.size) {
                    val recordNode = objectMapper.createObjectNode()
                    headers.zip(values).forEach { (header, value) ->
                        recordNode.put(header, value)
                    }
                    
                    // Add metadata fields
                    addMetadataFields(recordNode, query.key, query.bucket)
                    
                    emit(S3Record(data = recordNode, changes = emptyMap()))
                }
            }
        }
    }
    
    private fun readParquet(s3Client: S3ClientWrapper, query: SelectQuery): Flow<S3Record> = flow {
        val bytes = s3Client.getObjectAsBytes(query.bucket, query.key)
        
        // Create a temporary file to read parquet
        val tempFile = kotlin.io.path.createTempFile("temp", ".parquet").toFile()
        tempFile.writeBytes(bytes)
        
        try {
            val reader: ParquetReader<GenericRecord> = AvroParquetReader.builder<GenericRecord>(
                org.apache.parquet.hadoop.util.HadoopInputFile.fromPath(
                    org.apache.hadoop.fs.Path(tempFile.absolutePath),
                    org.apache.hadoop.conf.Configuration()
                )
            ).build()
            
            var record: GenericRecord? = reader.read()
            while (record != null) {
                val jsonNode = avroRecordToJson(record)
                addMetadataFields(jsonNode, query.key, query.bucket)
                emit(S3Record(data = jsonNode, changes = emptyMap()))
                record = reader.read()
            }
        } finally {
            tempFile.delete()
        }
    }
    
    private fun readAvro(s3Client: S3ClientWrapper, query: SelectQuery): Flow<S3Record> = flow {
        val bytes = s3Client.getObjectAsBytes(query.bucket, query.key)
        
        val reader = DataFileReader(
            ByteArraySeekableInput(bytes),
            GenericDatumReader<GenericRecord>()
        )
        
        reader.use {
            it.forEach { record ->
                val jsonNode = avroRecordToJson(record)
                addMetadataFields(jsonNode, query.key, query.bucket)
                emit(S3Record(data = jsonNode, changes = emptyMap()))
            }
        }
    }
    
    private fun readJsonl(s3Client: S3ClientWrapper, query: SelectQuery): Flow<S3Record> = flow {
        val inputStream = s3Client.getObjectInputStream(query.bucket, query.key)
        
        inputStream.use { stream ->
            val reader = BufferedReader(InputStreamReader(stream))
            
            reader.lineSequence().forEach { line ->
                try {
                    val json = objectMapper.readTree(line)
                    if (json is ObjectNode) {
                        addMetadataFields(json, query.key, query.bucket)
                    }
                    emit(S3Record(data = json, changes = emptyMap()))
                } catch (e: Exception) {
                    log.warn { "Failed to parse JSON line: $line" }
                }
            }
        }
    }
    
    private fun parseCsvLine(line: String, config: StreamConfiguration): List<String> {
        val delimiter = config.delimiter
        val quoteChar = config.quoteChar.firstOrNull() ?: '"'
        val escapeChar = config.escapeChar?.firstOrNull()
        
        val values = mutableListOf<String>()
        val currentValue = StringBuilder()
        var inQuotes = false
        var escaped = false
        
        for (char in line) {
            when {
                escaped -> {
                    currentValue.append(char)
                    escaped = false
                }
                escapeChar != null && char == escapeChar -> {
                    escaped = true
                }
                char == quoteChar -> {
                    inQuotes = !inQuotes
                }
                !inQuotes && char.toString() == delimiter -> {
                    values.add(currentValue.toString())
                    currentValue.clear()
                }
                else -> {
                    currentValue.append(char)
                }
            }
        }
        
        values.add(currentValue.toString())
        return values
    }
    
    private fun avroRecordToJson(record: GenericRecord): ObjectNode {
        val node = objectMapper.createObjectNode()
        
        record.schema.fields.forEach { field ->
            val value = record.get(field.name())
            when (value) {
                null -> node.putNull(field.name())
                is String -> node.put(field.name(), value)
                is Int -> node.put(field.name(), value)
                is Long -> node.put(field.name(), value)
                is Float -> node.put(field.name(), value)
                is Double -> node.put(field.name(), value)
                is Boolean -> node.put(field.name(), value)
                is GenericRecord -> node.set(field.name(), avroRecordToJson(value))
                else -> node.put(field.name(), value.toString())
            }
        }
        
        return node
    }
    
    private fun addMetadataFields(node: ObjectNode, key: String, bucket: String) {
        node.put("_ab_source_file_url", "s3://$bucket/$key")
        node.put("_ab_source_file_last_modified", Instant.now().toString())
    }
}

/**
 * Query for selecting records from an S3 file
 */
data class SelectQuery(
    val stream: Stream,
    val bucket: String,
    val key: String,
    val format: FileFormat,
    val streamConfig: StreamConfiguration
)

/**
 * Record read from S3
 */
data class S3Record(
    val data: JsonNode,
    val changes: Map<String, AirbyteRecordMessageMeta.Change>
)
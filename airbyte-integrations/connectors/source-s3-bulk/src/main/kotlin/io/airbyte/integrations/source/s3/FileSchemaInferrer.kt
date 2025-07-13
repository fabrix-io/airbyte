/* Copyright (c) 2024 Airbyte, Inc., all rights reserved. */
package io.airbyte.integrations.source.s3

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.dataformat.csv.CsvMapper
import com.fasterxml.jackson.dataformat.csv.CsvParser
import com.fasterxml.jackson.dataformat.csv.CsvSchema
import io.airbyte.cdk.discover.*
import io.github.oshai.kotlinlogging.KotlinLogging
import jakarta.inject.Singleton
import org.apache.avro.Schema
import org.apache.avro.file.DataFileReader
import org.apache.avro.generic.GenericDatumReader
import org.apache.avro.generic.GenericRecord
import org.apache.parquet.avro.AvroParquetReader
import org.apache.parquet.hadoop.ParquetReader
import java.io.BufferedReader
import java.io.ByteArrayInputStream
import java.io.InputStreamReader
import java.nio.charset.Charset

private val log = KotlinLogging.logger {}

@Singleton
class FileSchemaInferrer {
    
    private val objectMapper = ObjectMapper()
    private val csvMapper = CsvMapper().apply {
        enable(CsvParser.Feature.WRAP_AS_ARRAY)
    }

    fun parseJsonSchema(schemaStr: String): List<Field> {
        val schemaNode = objectMapper.readTree(schemaStr)
        return parseJsonSchemaNode(schemaNode)
    }

    private fun parseJsonSchemaNode(node: JsonNode): List<Field> {
        val fields = mutableListOf<Field>()
        
        if (node.has("properties")) {
            node.get("properties").fields().forEach { (fieldName, fieldSchema) ->
                val fieldType = inferFieldTypeFromJsonSchema(fieldSchema)
                fields.add(Field(id = fieldName, type = fieldType))
            }
        }
        
        return fields
    }

    private fun inferFieldTypeFromJsonSchema(schemaNode: JsonNode): FieldType {
        val type = schemaNode.get("type")?.asText() ?: return UnknownFieldType

        return when (type) {
            "string" -> StringFieldType
            "integer" -> IntegerFieldType
            "number" -> DoubleFieldType
            "boolean" -> BooleanFieldType
            "array" -> ArrayFieldType(UnknownFieldType)
            "object" -> ObjectFieldType(emptyList())
            else -> UnknownFieldType
        }
    }

    fun inferCsvSchema(
        s3Client: S3ClientWrapper,
        bucket: String,
        files: List<S3FileInfo>,
        delimiter: String,
        quoteChar: String,
        escapeChar: String?,
        encoding: String,
        skipRowsBeforeHeader: Int,
        autogenerateColumnNames: Boolean,
        columnNames: List<String>?
    ): List<Field> {
        if (files.isEmpty()) return emptyList()

        val file = files.first()
        val inputStream = s3Client.getObjectInputStream(bucket, file.key)
        
        return inputStream.use { stream ->
            val reader = BufferedReader(InputStreamReader(stream, Charset.forName(encoding)))
            
            // Skip rows before header
            repeat(skipRowsBeforeHeader) {
                reader.readLine()
            }
            
            // Get column names
            val headers = when {
                !columnNames.isNullOrEmpty() -> columnNames
                autogenerateColumnNames -> {
                    val firstLine = reader.readLine()
                    val numColumns = firstLine?.split(delimiter)?.size ?: 0
                    (1..numColumns).map { "column_$it" }
                }
                else -> {
                    val headerLine = reader.readLine()
                    headerLine?.split(delimiter)?.map { it.trim(quoteChar.first()) } ?: emptyList()
                }
            }
            
            // Sample some rows to infer types
            val sampleSize = 100
            val samples = mutableListOf<List<String>>()
            
            repeat(sampleSize) {
                val line = reader.readLine() ?: return@repeat
                samples.add(line.split(delimiter).map { it.trim(quoteChar.first()) })
            }
            
            // Infer field types
            headers.mapIndexed { index, header ->
                val columnValues = samples.mapNotNull { row ->
                    row.getOrNull(index)?.takeIf { it.isNotBlank() }
                }
                Field(id = header, type = inferFieldType(columnValues))
            }
        }
    }

    fun inferParquetSchema(
        s3Client: S3ClientWrapper,
        bucket: String,
        files: List<S3FileInfo>
    ): List<Field> {
        if (files.isEmpty()) return emptyList()

        val file = files.first()
        val bytes = s3Client.getObjectAsBytes(bucket, file.key)
        
        // Create a temporary file to read parquet
        val tempFile = kotlin.io.path.createTempFile("temp", ".parquet").toFile()
        tempFile.writeBytes(bytes)
        
        return try {
            val reader: ParquetReader<GenericRecord> = AvroParquetReader.builder<GenericRecord>(
                org.apache.parquet.hadoop.util.HadoopInputFile.fromPath(
                    org.apache.hadoop.fs.Path(tempFile.absolutePath),
                    org.apache.hadoop.conf.Configuration()
                )
            ).build()
            
            val record = reader.read()
            val schema = record?.schema
            
            schema?.fields?.map { field ->
                Field(
                    id = field.name(),
                    type = avroTypeToFieldType(field.schema())
                )
            } ?: emptyList()
        } finally {
            tempFile.delete()
        }
    }

    fun inferAvroSchema(
        s3Client: S3ClientWrapper,
        bucket: String,
        files: List<S3FileInfo>
    ): List<Field> {
        if (files.isEmpty()) return emptyList()

        val file = files.first()
        val bytes = s3Client.getObjectAsBytes(bucket, file.key)
        
        val reader = DataFileReader(
            ByteArraySeekableInput(bytes),
            GenericDatumReader<GenericRecord>()
        )
        
        return reader.use {
            val schema = it.schema
            schema.fields.map { field ->
                Field(
                    id = field.name(),
                    type = avroTypeToFieldType(field.schema())
                )
            }
        }
    }

    fun inferJsonlSchema(
        s3Client: S3ClientWrapper,
        bucket: String,
        files: List<S3FileInfo>
    ): List<Field> {
        if (files.isEmpty()) return emptyList()

        val file = files.first()
        val inputStream = s3Client.getObjectInputStream(bucket, file.key)
        
        return inputStream.use { stream ->
            val reader = BufferedReader(InputStreamReader(stream))
            val fieldMap = mutableMapOf<String, FieldType>()
            
            // Sample first 100 lines
            repeat(100) {
                val line = reader.readLine() ?: return@repeat
                try {
                    val json = objectMapper.readTree(line)
                    json.fields().forEach { (fieldName, fieldValue) ->
                        val fieldType = inferFieldTypeFromJsonValue(fieldValue)
                        fieldMap[fieldName] = fieldType
                    }
                } catch (e: Exception) {
                    log.warn { "Failed to parse JSON line: $line" }
                }
            }
            
            fieldMap.map { (name, type) ->
                Field(id = name, type = type)
            }
        }
    }

    private fun inferFieldType(values: List<String>): FieldType {
        if (values.isEmpty()) return StringFieldType

        val hasInteger = values.all { it.toIntOrNull() != null }
        if (hasInteger) return IntegerFieldType

        val hasDouble = values.all { it.toDoubleOrNull() != null }
        if (hasDouble) return DoubleFieldType

        val hasBoolean = values.all { it.equals("true", ignoreCase = true) || it.equals("false", ignoreCase = true) }
        if (hasBoolean) return BooleanFieldType

        return StringFieldType
    }

    private fun inferFieldTypeFromJsonValue(node: JsonNode): FieldType {
        return when {
            node.isTextual -> StringFieldType
            node.isInt || node.isLong -> IntegerFieldType
            node.isDouble || node.isFloat -> DoubleFieldType
            node.isBoolean -> BooleanFieldType
            node.isArray -> ArrayFieldType(UnknownFieldType)
            node.isObject -> ObjectFieldType(emptyList())
            else -> UnknownFieldType
        }
    }

    private fun avroTypeToFieldType(schema: Schema): FieldType {
        return when (schema.type) {
            Schema.Type.STRING -> StringFieldType
            Schema.Type.INT, Schema.Type.LONG -> IntegerFieldType
            Schema.Type.FLOAT, Schema.Type.DOUBLE -> DoubleFieldType
            Schema.Type.BOOLEAN -> BooleanFieldType
            Schema.Type.ARRAY -> ArrayFieldType(UnknownFieldType)
            Schema.Type.RECORD, Schema.Type.MAP -> ObjectFieldType(emptyList())
            Schema.Type.UNION -> {
                // For unions, pick the first non-null type
                val nonNullTypes = schema.types.filter { it.type != Schema.Type.NULL }
                if (nonNullTypes.isNotEmpty()) {
                    avroTypeToFieldType(nonNullTypes.first())
                } else {
                    UnknownFieldType
                }
            }
            else -> UnknownFieldType
        }
    }
}

/**
 * Custom SeekableInput implementation for Avro to read from byte array
 */
class ByteArraySeekableInput(private val bytes: ByteArray) : org.apache.avro.file.SeekableInput {
    private var position = 0L

    override fun read(b: ByteArray, off: Int, len: Int): Int {
        if (position >= bytes.size) return -1
        
        val available = (bytes.size - position).toInt()
        val toRead = minOf(len, available)
        
        System.arraycopy(bytes, position.toInt(), b, off, toRead)
        position += toRead
        
        return toRead
    }

    override fun seek(p: Long) {
        position = p
    }

    override fun tell(): Long = position

    override fun length(): Long = bytes.size.toLong()

    override fun close() {
        // Nothing to close
    }
}
/* Copyright (c) 2024 Airbyte, Inc., all rights reserved. */
package io.airbyte.integrations.source.s3

import com.fasterxml.jackson.annotation.JsonIgnore
import com.fasterxml.jackson.annotation.JsonProperty
import com.fasterxml.jackson.annotation.JsonPropertyDescription
import com.fasterxml.jackson.annotation.JsonPropertyOrder
import com.fasterxml.jackson.annotation.JsonSubTypes
import com.fasterxml.jackson.annotation.JsonTypeInfo
import com.kjetland.jackson.jsonSchema.annotations.JsonSchemaDefault
import com.kjetland.jackson.jsonSchema.annotations.JsonSchemaInject
import com.kjetland.jackson.jsonSchema.annotations.JsonSchemaTitle
import edu.umd.cs.findbugs.annotations.SuppressFBWarnings
import io.airbyte.cdk.command.CONNECTOR_CONFIG_PREFIX
import io.airbyte.cdk.command.ConfigurationSpecification
import io.micronaut.context.annotation.ConfigurationBuilder
import io.micronaut.context.annotation.ConfigurationProperties
import jakarta.inject.Singleton

/**
 * The object which is mapped to the S3 source configuration JSON.
 */
@JsonSchemaTitle("S3 Source Spec")
@JsonPropertyOrder(
    value = ["bucket", "aws_access_key_id", "aws_secret_access_key", "path_pattern", 
             "endpoint", "region_name", "start_date", "streams"],
)
@Singleton
@ConfigurationProperties(CONNECTOR_CONFIG_PREFIX)
@SuppressFBWarnings(value = ["NP_NONNULL_RETURN_VIOLATION"], justification = "Micronaut DI")
class S3SourceConfigurationSpecification : ConfigurationSpecification() {
    
    @JsonProperty("bucket")
    @JsonSchemaTitle("Bucket")
    @JsonPropertyDescription("Name of the S3 bucket where the file(s) exist.")
    @JsonSchemaInject(json = """{"order":0}""")
    lateinit var bucket: String

    @JsonProperty("aws_access_key_id")
    @JsonSchemaTitle("AWS Access Key ID")
    @JsonPropertyDescription(
        "In order to access private Buckets stored on AWS S3, this connector requires credentials with the proper " +
        "permissions. If accessing publicly available data, this field is not necessary."
    )
    @JsonSchemaInject(json = """{"order":1,"airbyte_secret":true,"always_show":true}""")
    var awsAccessKeyId: String? = null

    @JsonProperty("aws_secret_access_key")
    @JsonSchemaTitle("AWS Secret Access Key")
    @JsonPropertyDescription(
        "In order to access private Buckets stored on AWS S3, this connector requires credentials with the proper " +
        "permissions. If accessing publicly available data, this field is not necessary."
    )
    @JsonSchemaInject(json = """{"order":2,"airbyte_secret":true,"always_show":true}""")
    var awsSecretAccessKey: String? = null

    @JsonProperty("role_arn")
    @JsonSchemaTitle("AWS Role ARN")
    @JsonPropertyDescription(
        "Specifies the Amazon Resource Name (ARN) of an IAM role that you want to use to perform operations " +
        "requested using this profile. Set the External ID to the Airbyte workspace ID."
    )
    @JsonSchemaInject(json = """{"order":3}""")
    var roleArn: String? = null
    
    @JsonProperty("external_id")
    @JsonSchemaTitle("External ID")
    @JsonPropertyDescription("External ID to use when assuming a role. This is used for cross-account access using the role_arn parameter.")
    @JsonSchemaInject(json = """{"order":4,"airbyte_secret":true}""")
    var externalId: String? = null

    @JsonProperty("path_pattern")
    @JsonSchemaTitle("Path Pattern")
    @JsonPropertyDescription(
        "By default, the connector will list all files and then filter them using glob patterns. " +
        "This field defines the glob pattern(s) that will be used to match keys after they are listed " +
        "(CSV, Parquet, Avro and JSONL supported). Use | to separate multiple patterns."
    )
    @JsonSchemaInject(json = """{"order":8,"examples":["**/*.csv","**/*.parquet"]}""")
    @JsonSchemaDefault("**")
    var pathPattern: String = "**"

    @JsonProperty("endpoint")
    @JsonSchemaTitle("Endpoint")
    @JsonPropertyDescription("Endpoint to an S3 compatible service. Leave empty to use AWS.")
    @JsonSchemaInject(json = """{"order":9,"examples":["https://my-s3-compatible.com","http://localhost:9000"]}""")
    var endpoint: String? = null

    @JsonProperty("region_name")
    @JsonSchemaTitle("AWS Region")
    @JsonPropertyDescription("AWS region where the S3 bucket is located. If not provided, the region will be determined automatically.")
    @JsonSchemaInject(json = """{"order":10,"examples":["us-east-1","eu-west-2"]}""")
    var regionName: String? = null

    @JsonProperty("start_date")
    @JsonSchemaTitle("Start Date")
    @JsonPropertyDescription(
        "UTC date and time in the format 2017-01-25T00:00:00.000Z. Any file with a " +
        "last modified date older than this will be excluded."
    )
    @JsonSchemaInject(json = """{"order":11,"format":"date-time","examples":["2021-01-01T00:00:00.000Z"]}""")
    var startDate: String? = null

    @JsonProperty("streams")
    @JsonSchemaTitle("Streams")
    @JsonPropertyDescription("The list of streams to sync. Each stream configuration includes name, format, and other settings.")
    @JsonSchemaInject(json = """{"order":12}""")
    var streams: List<StreamConfiguration> = emptyList()

    @JsonIgnore
    @ConfigurationBuilder(configurationPrefix = "request_timeout")
    var requestTimeout: RequestTimeoutConfiguration = RequestTimeoutConfiguration()

    @JsonIgnore
    @ConfigurationBuilder(configurationPrefix = "max_concurrent_requests")
    var maxConcurrentRequests: Int = 10

    @JsonIgnore
    @ConfigurationBuilder(configurationPrefix = "max_retries")
    var maxRetries: Int = 3

    @JsonIgnore
    @ConfigurationBuilder(configurationPrefix = "retry_backoff_ms")
    var retryBackoffMs: Long = 1000

    @JsonProperty("use_ssl")
    @JsonSchemaTitle("Use SSL")
    @JsonPropertyDescription("Whether to use SSL when connecting to S3. Only relevant when using a custom endpoint.")
    @JsonSchemaDefault("true")
    var useSsl: Boolean = true

    @JsonProperty("verify_ssl_cert")
    @JsonSchemaTitle("Verify SSL Certificate")
    @JsonPropertyDescription("Whether to verify SSL certificates. Only relevant when using a custom endpoint with SSL.")
    @JsonSchemaDefault("true")
    var verifySslCert: Boolean = true
}

/**
 * Configuration for a single stream (table) to sync from S3
 */
data class StreamConfiguration(
    @JsonProperty("name")
    @JsonSchemaTitle("Stream Name")
    @JsonPropertyDescription("The name of the stream (table) to sync")
    val name: String,

    @JsonProperty("format")
    @JsonSchemaTitle("File Format")
    @JsonPropertyDescription("The format of the files to sync for this stream")
    val format: FileFormat,

    @JsonProperty("globs")
    @JsonSchemaTitle("Globs")
    @JsonPropertyDescription(
        "Glob patterns to match files for this stream. Use '**' to match all subdirectories."
    )
    @JsonSchemaInject(json = """{"examples":["**/*.csv","data/*.parquet"]}""")
    val globs: List<String>? = null,

    @JsonProperty("input_schema")
    @JsonSchemaTitle("Input Schema")
    @JsonPropertyDescription("The schema that will be used for this stream. Can be a string or JSON object.")
    val inputSchema: String? = null,

    @JsonProperty("primary_key")
    @JsonSchemaTitle("Primary Key")
    @JsonPropertyDescription("The primary key of the stream (table) to sync")
    val primaryKey: String? = null,

    @JsonProperty("delimiter")
    @JsonSchemaTitle("Delimiter")
    @JsonPropertyDescription("The delimiter to use for CSV files. Default is ','.")
    @JsonSchemaDefault(",")
    val delimiter: String = ",",

    @JsonProperty("quote_char")
    @JsonSchemaTitle("Quote Character")
    @JsonPropertyDescription("The character used to quote CSV fields. Default is '\"'.")
    @JsonSchemaDefault("\"")
    val quoteChar: String = "\"",

    @JsonProperty("escape_char")
    @JsonSchemaTitle("Escape Character")
    @JsonPropertyDescription("The character used to escape special characters. Default is null.")
    val escapeChar: String? = null,

    @JsonProperty("encoding")
    @JsonSchemaTitle("Encoding")
    @JsonPropertyDescription("The encoding of the files. Default is 'utf-8'.")
    @JsonSchemaDefault("utf-8")
    val encoding: String = "utf-8",

    @JsonProperty("double_quote")
    @JsonSchemaTitle("Double Quote")
    @JsonPropertyDescription("Whether to double-quote quotes in CSV. Default is true.")
    @JsonSchemaDefault("true")
    val doubleQuote: Boolean = true,

    @JsonProperty("skip_rows_before_header")
    @JsonSchemaTitle("Skip Rows Before Header")
    @JsonPropertyDescription("Number of rows to skip before the header row.")
    @JsonSchemaDefault("0")
    val skipRowsBeforeHeader: Int = 0,

    @JsonProperty("skip_rows_after_header")
    @JsonSchemaTitle("Skip Rows After Header")
    @JsonPropertyDescription("Number of rows to skip after the header row.")
    @JsonSchemaDefault("0")
    val skipRowsAfterHeader: Int = 0,

    @JsonProperty("autogenerate_column_names")
    @JsonSchemaTitle("Autogenerate Column Names")
    @JsonPropertyDescription("Whether to autogenerate column names if they are not provided.")
    @JsonSchemaDefault("false")
    val autogenerateColumnNames: Boolean = false,

    @JsonProperty("column_names")
    @JsonSchemaTitle("Column Names")
    @JsonPropertyDescription("List of column names to use (overrides header row).")
    val columnNames: List<String>? = null
)

/**
 * File format enumeration
 */
@JsonTypeInfo(use = JsonTypeInfo.Id.NAME, property = "filetype")
@JsonSubTypes(
    JsonSubTypes.Type(value = FileFormat.CsvFormat::class, name = "csv"),
    JsonSubTypes.Type(value = FileFormat.ParquetFormat::class, name = "parquet"),
    JsonSubTypes.Type(value = FileFormat.AvroFormat::class, name = "avro"),
    JsonSubTypes.Type(value = FileFormat.JsonlFormat::class, name = "jsonl")
)
sealed class FileFormat {
    @JsonSchemaTitle("CSV")
    data class CsvFormat(
        @JsonProperty("filetype")
        @JsonSchemaDefault("csv")
        val filetype: String = "csv"
    ) : FileFormat()

    @JsonSchemaTitle("Parquet")
    data class ParquetFormat(
        @JsonProperty("filetype")
        @JsonSchemaDefault("parquet")
        val filetype: String = "parquet"
    ) : FileFormat()

    @JsonSchemaTitle("Avro")
    data class AvroFormat(
        @JsonProperty("filetype")
        @JsonSchemaDefault("avro")
        val filetype: String = "avro"
    ) : FileFormat()

    @JsonSchemaTitle("JSONL")
    data class JsonlFormat(
        @JsonProperty("filetype")
        @JsonSchemaDefault("jsonl")
        val filetype: String = "jsonl"
    ) : FileFormat()
}

/**
 * Request timeout configuration
 */
data class RequestTimeoutConfiguration(
    val connect: Long = 30_000,
    val read: Long = 300_000
)
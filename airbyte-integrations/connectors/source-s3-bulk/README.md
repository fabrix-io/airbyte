# S3 Source Connector (Bulk Extract CDK)

This is the S3 source connector implemented using the Bulk Extract CDK in Kotlin. It provides the same functionality as the Python-based source-s3 connector but leverages the performance improvements of the Bulk Extract CDK.

## Features

- Supports multiple file formats: CSV, Parquet, Avro, and JSONL
- AWS S3 and S3-compatible storage support
- IAM role assumption for cross-account access
- Incremental sync based on file modification time
- Multi-stream configuration
- Schema inference and custom schema support
- Parallel file processing for improved performance

## Configuration

### Required Parameters

- `bucket`: The S3 bucket name
- `streams`: List of streams to sync, each with:
  - `name`: Stream name
  - `format`: File format (csv, parquet, avro, jsonl)
  - `globs`: Optional glob patterns to match files

### Optional Parameters

- `aws_access_key_id`: AWS Access Key ID (for private buckets)
- `aws_secret_access_key`: AWS Secret Access Key (for private buckets)
- `role_arn`: AWS Role ARN for cross-account access
- `external_id`: External ID for role assumption
- `path_pattern`: Global path pattern for file matching (default: "**")
- `endpoint`: Custom S3 endpoint for S3-compatible services
- `region_name`: AWS region
- `start_date`: Filter files modified after this date

### Stream-specific Configuration

Each stream can have additional configuration options:

#### CSV Options
- `delimiter`: Field delimiter (default: ",")
- `quote_char`: Quote character (default: "\"")
- `escape_char`: Escape character
- `encoding`: File encoding (default: "utf-8")
- `skip_rows_before_header`: Number of rows to skip before header
- `skip_rows_after_header`: Number of rows to skip after header
- `autogenerate_column_names`: Whether to auto-generate column names
- `column_names`: Explicit column names

## Building

```bash
./gradlew :airbyte-integrations:connectors:source-s3-bulk:build
```

## Running

The connector follows the Airbyte protocol and supports the standard commands:

```bash
# Spec
java -jar build/libs/source-s3-bulk.jar spec

# Check
java -jar build/libs/source-s3-bulk.jar check --config config.json

# Discover
java -jar build/libs/source-s3-bulk.jar discover --config config.json

# Read
java -jar build/libs/source-s3-bulk.jar read --config config.json --catalog catalog.json --state state.json
```

## Example Configuration

```json
{
  "bucket": "my-s3-bucket",
  "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  "streams": [
    {
      "name": "customers",
      "format": { "filetype": "csv" },
      "globs": ["customers/*.csv"],
      "delimiter": ",",
      "quote_char": "\""
    },
    {
      "name": "products",
      "format": { "filetype": "parquet" },
      "globs": ["products/*.parquet"]
    }
  ]
}
```

## Development

This connector is built using:
- Kotlin
- Bulk Extract CDK
- AWS SDK v2
- Apache Parquet
- Apache Avro
- Jackson for JSON/CSV processing

## License

This connector is licensed under the Elastic License 2.0 (ELv2).
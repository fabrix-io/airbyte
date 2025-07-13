/* Copyright (c) 2024 Airbyte, Inc., all rights reserved. */
package io.airbyte.integrations.source.s3

import io.github.oshai.kotlinlogging.KotlinLogging
import jakarta.inject.Inject
import jakarta.inject.Singleton
import software.amazon.awssdk.auth.credentials.*
import software.amazon.awssdk.core.client.config.ClientOverrideConfiguration
import software.amazon.awssdk.regions.Region
import software.amazon.awssdk.services.s3.S3Client
import software.amazon.awssdk.services.s3.S3ClientBuilder
import software.amazon.awssdk.services.s3.model.*
import software.amazon.awssdk.services.sts.StsClient
import software.amazon.awssdk.services.sts.model.AssumeRoleRequest
import java.net.URI
import java.time.Duration
import java.time.Instant
import kotlin.streams.asSequence

private val log = KotlinLogging.logger {}

@Singleton
class S3ClientFactory @Inject constructor(
    private val config: S3SourceConfiguration
) : AutoCloseable {

    private val stsClient: StsClient? by lazy {
        if (config.roleArn != null) {
            StsClient.builder()
                .credentialsProvider(getBaseCredentialsProvider())
                .build()
        } else {
            null
        }
    }

    fun createClient(): S3ClientWrapper {
        val s3ClientBuilder = S3Client.builder()

        // Configure credentials
        s3ClientBuilder.credentialsProvider(getCredentialsProvider())

        // Configure region
        if (!config.regionName.isNullOrBlank()) {
            s3ClientBuilder.region(Region.of(config.regionName))
        } else {
            s3ClientBuilder.region(Region.US_EAST_1)
        }

        // Configure endpoint for S3-compatible services
        if (!config.endpoint.isNullOrBlank()) {
            val uri = URI.create(config.endpoint)
            s3ClientBuilder.endpointOverride(uri)
            
            // For non-AWS S3 endpoints, we need to enable path-style access
            s3ClientBuilder.forcePathStyle(true)
        }

        // Configure client overrides (timeouts, retries)
        val overrideConfig = ClientOverrideConfiguration.builder()
            .apiCallTimeout(Duration.ofMillis(config.requestTimeout.read))
            .apiCallAttemptTimeout(Duration.ofMillis(config.requestTimeout.connect))
            .build()
        s3ClientBuilder.overrideConfiguration(overrideConfig)

        return S3ClientWrapper(s3ClientBuilder.build())
    }

    private fun getBaseCredentialsProvider(): AwsCredentialsProvider {
        return when {
            !config.awsAccessKeyId.isNullOrBlank() && !config.awsSecretAccessKey.isNullOrBlank() -> {
                StaticCredentialsProvider.create(
                    AwsBasicCredentials.create(config.awsAccessKeyId, config.awsSecretAccessKey)
                )
            }
            else -> DefaultCredentialsProvider.create()
        }
    }

    private fun getCredentialsProvider(): AwsCredentialsProvider {
        return when {
            config.roleArn != null -> {
                // Use STS to assume role
                AssumeRoleCredentialsProvider(
                    stsClient = stsClient!!,
                    roleArn = config.roleArn,
                    sessionName = "airbyte-s3-source-${System.currentTimeMillis()}",
                    externalId = config.externalId
                )
            }
            else -> getBaseCredentialsProvider()
        }
    }

    override fun close() {
        stsClient?.close()
    }
}

/**
 * Wrapper around S3Client with convenience methods
 */
class S3ClientWrapper(
    private val s3Client: S3Client
) : AutoCloseable {

    fun listFiles(
        bucket: String,
        globs: List<String>,
        startDate: Instant?
    ): Sequence<S3FileInfo> {
        return s3Client.listObjectsV2Paginator(
            ListObjectsV2Request.builder()
                .bucket(bucket)
                .build()
        ).contents()
            .asSequence()
            .filter { obj ->
                // Filter by start date if provided
                startDate == null || obj.lastModified() >= startDate
            }
            .filter { obj ->
                // Filter by glob patterns
                globs.any { glob ->
                    matchesGlob(obj.key(), glob)
                }
            }
            .map { obj ->
                S3FileInfo(
                    key = obj.key(),
                    size = obj.size(),
                    lastModified = obj.lastModified(),
                    etag = obj.eTag()
                )
            }
    }

    fun getObject(bucket: String, key: String): GetObjectResponse {
        return s3Client.getObject(
            GetObjectRequest.builder()
                .bucket(bucket)
                .key(key)
                .build()
        )
    }

    fun getObjectAsBytes(bucket: String, key: String): ByteArray {
        return s3Client.getObjectAsBytes(
            GetObjectRequest.builder()
                .bucket(bucket)
                .key(key)
                .build()
        ).asByteArray()
    }

    fun getObjectInputStream(bucket: String, key: String): java.io.InputStream {
        return s3Client.getObject(
            GetObjectRequest.builder()
                .bucket(bucket)
                .key(key)
                .build()
        )
    }

    fun testConnection(bucket: String): Boolean {
        return try {
            s3Client.headBucket(
                HeadBucketRequest.builder()
                    .bucket(bucket)
                    .build()
            )
            true
        } catch (e: Exception) {
            log.error { "Failed to connect to S3 bucket $bucket: ${e.message}" }
            false
        }
    }

    private fun matchesGlob(path: String, glob: String): Boolean {
        // Convert glob pattern to regex
        val regex = glob
            .replace(".", "\\.")
            .replace("**", ".*")
            .replace("*", "[^/]*")
            .replace("?", ".")
        
        return path.matches(regex.toRegex())
    }

    override fun close() {
        s3Client.close()
    }
}

/**
 * Simple data class to hold S3 file information
 */
data class S3FileInfo(
    val key: String,
    val size: Long,
    val lastModified: Instant,
    val etag: String?
)

/**
 * Custom AssumeRole credentials provider
 */
class AssumeRoleCredentialsProvider(
    private val stsClient: StsClient,
    private val roleArn: String,
    private val sessionName: String,
    private val externalId: String?
) : AwsCredentialsProvider {
    
    override fun resolveCredentials(): AwsCredentials {
        val assumeRoleRequestBuilder = AssumeRoleRequest.builder()
            .roleArn(roleArn)
            .roleSessionName(sessionName)
        
        externalId?.let {
            assumeRoleRequestBuilder.externalId(it)
        }
        
        val response = stsClient.assumeRole(assumeRoleRequestBuilder.build())
        val credentials = response.credentials()
        
        return AwsSessionCredentials.create(
            credentials.accessKeyId(),
            credentials.secretAccessKey(),
            credentials.sessionToken()
        )
    }
}
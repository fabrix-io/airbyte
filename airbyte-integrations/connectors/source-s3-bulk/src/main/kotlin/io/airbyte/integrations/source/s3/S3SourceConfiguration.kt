/* Copyright (c) 2024 Airbyte, Inc., all rights reserved. */
package io.airbyte.integrations.source.s3

import io.airbyte.cdk.command.ConfigurationSpecificationSupplier
import io.airbyte.cdk.command.SourceConfiguration
import io.airbyte.cdk.command.SourceConfigurationFactory
import io.airbyte.cdk.ssh.SshConnectionOptions
import io.airbyte.cdk.ssh.SshNoTunnelMethod
import io.airbyte.cdk.ssh.SshTunnelMethodConfiguration
import io.micronaut.context.annotation.Factory
import jakarta.inject.Inject
import jakarta.inject.Singleton
import java.time.Duration
import java.time.Instant
import java.time.format.DateTimeFormatter

/** S3-specific implementation of [SourceConfiguration] */
data class S3SourceConfiguration(
    val bucketName: String,
    val awsAccessKeyId: String?,
    val awsSecretAccessKey: String?,
    val roleArn: String?,
    val externalId: String?,
    val pathPattern: String,
    val endpoint: String?,
    val regionName: String?,
    val startDate: Instant?,
    val streams: List<StreamConfiguration>,
    val requestTimeout: RequestTimeoutConfiguration,
    val maxConcurrentRequests: Int,
    val maxRetries: Int,
    val retryBackoffMs: Long,
    val useSsl: Boolean,
    val verifySslCert: Boolean,
    override val maxConcurrency: Int,
    override val resourceAcquisitionHeartbeat: Duration = Duration.ofMillis(100L),
    override val checkpointTargetInterval: Duration = Duration.ofMinutes(15),
) : SourceConfiguration {
    override val global: Boolean = false
    override val maxSnapshotReadDuration: Duration? = null
    override val sshTunnel: SshTunnelMethodConfiguration? = null
    override val sshConnectionOptions: SshConnectionOptions = SshConnectionOptions.DISABLED

    /** Required to inject [S3SourceConfiguration] directly. */
    @Factory
    private class MicronautFactory {
        @Singleton
        fun s3SourceConfig(
            factory: SourceConfigurationFactory<S3SourceConfigurationSpecification, S3SourceConfiguration>,
            supplier: ConfigurationSpecificationSupplier<S3SourceConfigurationSpecification>,
        ): S3SourceConfiguration = factory.make(supplier.get())
    }
}

@Singleton
class S3SourceConfigurationFactory @Inject constructor() :
    SourceConfigurationFactory<S3SourceConfigurationSpecification, S3SourceConfiguration> {

    override fun makeWithoutExceptionHandling(
        pojo: S3SourceConfigurationSpecification,
    ): S3SourceConfiguration {
        // Parse start date if provided
        val startDate = pojo.startDate?.let {
            Instant.from(DateTimeFormatter.ISO_INSTANT.parse(it))
        }

        return S3SourceConfiguration(
            bucketName = pojo.bucket,
            awsAccessKeyId = pojo.awsAccessKeyId,
            awsSecretAccessKey = pojo.awsSecretAccessKey,
            roleArn = pojo.roleArn,
            externalId = pojo.externalId,
            pathPattern = pojo.pathPattern,
            endpoint = pojo.endpoint,
            regionName = pojo.regionName,
            startDate = startDate,
            streams = pojo.streams,
            requestTimeout = pojo.requestTimeout,
            maxConcurrentRequests = pojo.maxConcurrentRequests,
            maxRetries = pojo.maxRetries,
            retryBackoffMs = pojo.retryBackoffMs,
            useSsl = pojo.useSsl,
            verifySslCert = pojo.verifySslCert,
            maxConcurrency = pojo.maxConcurrentRequests,
        )
    }
}
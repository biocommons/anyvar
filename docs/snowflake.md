# AnyVar Snowflake Setup

AnyVar can utilize Snowflake, a cloud-based data warehouse, to store and manage large-scale variation data efficiently. This integration is beneficial for high-volume or enterprise-level environments that require scalability, reliability, and robust analytics.

## When to Use Snowflake

Snowflake is recommended for scenarios where significant data scale, performance, cloud storage capabilities, and complex analytical queries are essential.

## Step-by-Step Snowflake Setup

Follow these detailed steps to configure Snowflake for AnyVar.

### 1. Preparing Your Snowflake Environment

* Ensure you have a valid Snowflake account and appropriate permissions.
* Create a dedicated database and schema within your Snowflake environment.

### 2. Schema Creation

Run the following SQL command to set up the minimal required table schema:

```sql
CREATE TABLE vrs_objects (
    vrs_id VARCHAR(500) COLLATE 'utf8',
    vrs_object VARIANT
);
```

This setup meets AnyVar’s minimal requirements to store variant data.

## Snowflake Connection Setup

Set the environment variable to allow AnyVar to connect with your Snowflake instance:

```shell
export ANYVAR_STORAGE_URI=snowflake://<username>:<password>@<account_identifier>/<database_name>/<schema_name>
```

Replace `<username>`, `<password>`, `<account_identifier>`, `<database_name>`, and `<schema_name>` with your Snowflake credentials and details.

### Using Encrypted Private Keys (Optional)

Snowflake allows authentication using encrypted private keys:

```shell
export ANYVAR_STORAGE_URI=snowflake://<username>@<account_identifier>/<database_name>/<schema_name>?private_key=<path_to_your_private_key>
```

You can also embed URL-encoded private keys directly into your connection string.

## Advanced Configuration

### Batch Operation Modes

AnyVar supports multiple batch operation modes with Snowflake:

* `merge`: Ensures no duplicate VRS IDs are added, locking tables and reducing concurrency.
* `insert_notin`: Inserts new data without strict locking, improving concurrency.
* `insert`: High-throughput insertion without duplicate checking (not recommended for all scenarios).

Configure batch mode using:

```shell
export ANYVAR_SNOWFLAKE_BATCH_ADD_MODE=merge
```

### Environment Variables

| Variable                                        | Description                                              | Example                                   |
| ----------------------------------------------- | -------------------------------------------------------- | ----------------------------------------- |
| `ANYVAR_STORAGE_URI`                            | Snowflake connection URL                                 | `snowflake://user:pass@account/db/schema` |
| `ANYVAR_SNOWFLAKE_BATCH_ADD_MODE`               | Batch insertion mode (`merge`, `insert_notin`, `insert`) | `merge`                                   |
| `ANYVAR_SNOWFLAKE_STORE_PRIVATE_KEY_PASSPHRASE` | Passphrase for encrypted private keys                    | `<passphrase>`                            |

## Security Considerations

* Ensure credentials and private keys are securely stored and managed.
* Regularly rotate credentials and use secure connection settings (e.g., encrypted private keys).
* Follow Snowflake’s best practices for security and compliance.

## Verifying Snowflake Setup

Use Snowflake CLI or a compatible client to test connectivity:

```shell
snowsql -a <account_identifier> -u <username>
```

Perform a simple query to verify setup:

```sql
SELECT COUNT(*) FROM vrs_objects;
```

Successful results indicate a correctly configured Snowflake environment.

## Troubleshooting Tips

* **Connection Issues:** Verify account credentials, account identifiers, and network permissions.
* **Permission Errors:** Ensure the Snowflake user has proper permissions for schema creation and data manipulation.
* **Batch Operations:** Adjust `ANYVAR_SNOWFLAKE_BATCH_ADD_MODE` if performance issues occur during bulk inserts.

---

Your Snowflake setup is now ready to integrate with AnyVar. Refer to the main AnyVar documentation for further operational guidance.

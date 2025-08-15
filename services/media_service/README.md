## Setting up Minio

### Steps to Create a New User for Your REST API
Your goal is to create the user `products` with the secret key `secure-super-secret-random-32-characters!` for your FastAPI application, using commands inside the `infra-minio-1` container. Here’s the focused solution:

1. **Access the MinIO Container**:
   ```bash
   docker exec -it infra-minio-1 /bin/sh
   ```

2. **Set Up the MinIO Alias**:
   Configure `mc` to connect to the MinIO server using the root credentials:
   ```bash
   mc alias set myminio http://localhost:9000 admin admin1234
   ```
   Verify the alias:
   ```bash
   mc admin info myminio
   ```
   If this fails (e.g., authentication error), ensure `admin:admin1234` matches your `.env` file’s `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`.

3. **Create the `products` User**:
   Add the user with the credentials from your `.env` file:
   ```bash
   mc admin user add myminio products secure-super-secret-random-32-characters!
   ```
   Verify the user was created:
   ```bash
   mc admin user list myminio
   ```
   Look for `products` with status `enabled`.

4. **Create and Assign a Policy for the `products` Bucket**:
   Create a policy file:
   ```bash
   echo '{
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": ["s3:*"],
         "Resource": ["arn:aws:s3:::products/*"]
       },
       {
         "Effect": "Allow",
         "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
         "Resource": ["arn:aws:s3:::products"]
       }
     ]
   }' > /data/products-readwrite.json
   ```
   Add the policy:
   ```bash
   mc admin policy create myminio products-readwrite /data/products-readwrite.json
   ```
   Attach the policy to the user:
   ```bash
   mc admin policy attach myminio products-readwrite --user products
   ```

5. **Create the `products` Bucket**:
   ```bash
   mc mb myminio/products
   ```
   Verify:
   ```bash
   mc ls myminio
   ```

6. **Test the New User**:
   ```bash
   mc alias set myminio-app http://localhost:9000 products secure-super-secret-random-32-characters!
   mc ls myminio-app
   ```
   If this lists the `products` bucket (or returns no error), the user is correctly configured.
   Exit the container:
   ```bash
   exit
   ```
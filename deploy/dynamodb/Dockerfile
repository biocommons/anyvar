FROM eclipse-temurin:17

WORKDIR /app

RUN apt-get update && apt-get install -y unzip

RUN curl -O https://s3.us-west-2.amazonaws.com/dynamodb-local/dynamodb_local_latest.tar.gz \
    && tar -xzf dynamodb_local_latest.tar.gz \
    && rm dynamodb_local_latest.tar.gz

# it'd be nice to get a defined "latest" ddb copy somehow
RUN curl -O https://vicc-normalizers.s3.us-east-2.amazonaws.com/gene_normalization/dynamodb/shared-local-instance20221026.db.zip \
    && unzip shared-local-instance20221026.db.zip \
    && rm shared-local-instance20221026.db.zip

CMD java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar -sharedDb

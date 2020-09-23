FROM biocommons/dockerbase:1.0

COPY . /app/
WORKDIR /app
RUN python3 setup.py install

EXPOSE 5001

CMD ["python3", "-m", "anyvar.restapi"]

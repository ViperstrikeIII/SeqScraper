FROM python:3.12

RUN pip install requests

COPY id_mapper.py code/id_mapper.py

RUN chmod a+x /code/id_mapper.py

ENV PATH="/code:$PATH"
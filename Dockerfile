FROM python:3.13-alpine

WORKDIR /opt/rdgen

COPY . .
ENV PYTHONPATH=/opt/rdgen
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget --spider 0.0.0.0:8000

CMD ["sh", "-c", "python manage.py migrate && gunicorn -c gunicorn.conf.py rdgen.wsgi:application"]

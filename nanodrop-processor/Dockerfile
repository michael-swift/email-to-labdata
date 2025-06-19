FROM public.ecr.aws/lambda/python:3.12

# Copy requirements and install packages
COPY deploy/requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

# Copy function code
COPY src/lambda_function.py ${LAMBDA_TASK_ROOT}
COPY src/security_config.py ${LAMBDA_TASK_ROOT}
COPY src/structured_logger.py ${LAMBDA_TASK_ROOT}
COPY src/dynamodb_schema.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD ["lambda_function.lambda_handler"]
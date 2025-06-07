FROM public.ecr.aws/lambda/python:3.11

# Copy requirements and install packages
COPY lambda_requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r lambda_requirements.txt

# Copy function code
COPY lambda_function.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler
CMD ["lambda_function.lambda_handler"]
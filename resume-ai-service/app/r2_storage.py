import os
import boto3
from dotenv import load_dotenv

load_dotenv()

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=os.getenv('R2_URL'),
        aws_access_key_id=os.getenv('ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('SECRET_ACCESS_KEY'),
        region_name='auto'
    )

def list_r2_vtt_files() -> list[str]:
    """Lista todos os arquivos .vtt no bucket do R2."""
    s3 = get_s3_client()
    bucket = os.getenv('BUCKET_NAME', 'hackathon-traders-vtt')
    
    # Para o hackathon (<1000 arquivos), list_objects_v2 direto é o suficiente
    response = s3.list_objects_v2(Bucket=bucket)
    files = []
    
    if 'Contents' in response:
        for item in response['Contents']:
            if item['Key'].endswith('.vtt'):
                files.append(item['Key'])
    return files

def get_r2_vtt_content(file_key: str) -> str:
    """Baixa o conteúdo de texto de um arquivo específico no R2."""
    s3 = get_s3_client()
    bucket = os.getenv('BUCKET_NAME', 'hackathon-traders-vtt')
    response = s3.get_object(Bucket=bucket, Key=file_key)
    return response['Body'].read().decode('utf-8')
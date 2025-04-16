import boto3
import time
from botocore.config import Config

class TextractService:
    def __init__(self, aws_access_key, aws_secret_key, region):
        # Configure timeouts
        config = Config(
            connect_timeout=1160,
            read_timeout=1160,
            retries={'max_attempts': 3}
        )
        
        # Initialize Textract client
        self.textract = boto3.client(
            'textract',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=region,
            config=config
        )
        
        # Initialize S3 client
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=region,
            config=config
        )
        self.bucket_name = 'sperow-medical-records'

    def upload_to_s3(self, file_bytes, file_name):
        """Upload file to S3"""
        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=f'uploads/{file_name}',
                Body=file_bytes
            )
            return f'uploads/{file_name}'
        except Exception as e:
            print(f"Error uploading to S3: {str(e)}")
            return None

    def extract_text(self, file_bytes, file_name):
        """Extract text using Textract's async API via S3"""
        try:
            # Upload to S3
            s3_path = self.upload_to_s3(file_bytes, file_name)
            if not s3_path:
                return None

            # Start async Textract job
            response = self.textract.start_document_text_detection(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': self.bucket_name,
                        'Name': s3_path
                    }
                }
            )
            job_id = response['JobId']

            # Wait for completion
            while True:
                response = self.textract.get_document_text_detection(JobId=job_id)
                status = response['JobStatus']
                
                if status == 'SUCCEEDED':
                    text_blocks = []
                    pages = [response]
                    
                    # Get all pages
                    while 'NextToken' in response:
                        response = self.textract.get_document_text_detection(
                            JobId=job_id,
                            NextToken=response['NextToken']
                        )
                        pages.append(response)
                    
                    # Extract text from all pages
                    for page in pages:
                        for item in page['Blocks']:
                            if item['BlockType'] == 'LINE':
                                text_blocks.append(item['Text'])
                    
                    # Cleanup S3
                    self.s3.delete_object(
                        Bucket=self.bucket_name,
                        Key=s3_path
                    )
                    
                    return ' '.join(text_blocks)
                
                elif status == 'FAILED':
                    print("Document analysis failed")
                    return None
                
                time.sleep(2)  # Wait before checking status again

        except Exception as e:
            print(f"Error in text extraction: {str(e)}")
            return None 
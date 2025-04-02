from text_extractor import TextExtractor
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_and_process():
    try:
        extractor = TextExtractor()
        pdf_path = "attached_assets/fraud.pdf"

        logger.info("Starting text extraction from PDF")
        extracted_text = extractor.extract_text_from_pdf(pdf_path)

        # Split into examples based on newlines and filtering
        examples = [
            text.strip() for text in extracted_text.split('\n') 
            if text.strip() and len(text.strip()) > 20  # Only keep meaningful segments
        ]

        logger.info(f"Extracted {len(examples)} potential training examples")

        # Save processed examples for review
        with open('processed_examples.json', 'w') as f:
            json.dump(examples, f, indent=2)

        return examples

    except Exception as e:
        logger.error(f"Error during extraction and processing: {str(e)}")
        raise

if __name__ == "__main__":
    extract_and_process()
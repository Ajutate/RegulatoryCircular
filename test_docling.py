from services.document_extractor import DocumentExtractor
from services.paragraph_splitter import ParagraphSplitter
import os

extractor = DocumentExtractor()
with open('C:/Users/gorad/.gemini/antigravity-ide/brain/6e2ef04b-b91d-4993-97bc-7b852c1b2e70/.user_uploaded/media_1787721728245.pdf', 'rb') as f:
    text = extractor.extract(f.read(), 'media_1787721728245.pdf')

with open('docling_output.md', 'w', encoding='utf-8') as f:
    f.write(text)

splitter = ParagraphSplitter()
paragraphs = splitter.split(text)

with open('extracted_output.txt', 'w', encoding='utf-8') as f:
    for i, p in enumerate(paragraphs):
        f.write(f"PARA {i}:\n{p}\n\n")

print("Done! Check docling_output.md and extracted_output.txt")
print("Retail Banking in output?", "Retail Banking" in text)
print("Retail Banking in filtered paragraphs?", any("Retail Banking" in p for p in paragraphs))

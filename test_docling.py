import sys
sys.path.insert(0, "d:/AI POCs/RegulatoryCircular")

from services.document_extractor import DocumentExtractor
from services.paragraph_splitter import ParagraphSplitter

def main():
    try:
        ext = DocumentExtractor()
        with open('C:/Users/gorad/.gemini/antigravity-ide/brain/2aa33c9f-7d93-4de6-8e7f-f866883a7eec/.user_uploaded/media_1786704710065.pdf', 'rb') as f:
            file_bytes = f.read()
            
        print("Extracting with Docling...")
        text = ext.extract(file_bytes, "media_1786704710065.pdf")
        
        print("--- DOCLING MARKDOWN OUTPUT ---")
        print(text[:1000] + "...\n(truncated)\n")
        
        print("Splitting...")
        splitter = ParagraphSplitter()
        paras = splitter.split(text)
        
        print(f"--- SPLIT PARAGRAPHS ({len(paras)}) ---")
        for i, p in enumerate(paras):
            print(f"[{i+1}] {p}")
            print("-" * 40)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

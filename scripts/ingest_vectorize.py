import fitz
import os
from dotenv import load_dotenv

load_dotenv()

from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma

# 기본 경로 설정
PDF_SOURCE_DIR = "../data/source_documents"
MEDIA_SAVE_PATH = "../data/media_assets"
DB_PATH = "../data/vectorstore/chromadb_rag"


# PyMUPDF로 PDF 처리
def sanitize_filename(filename):
    """Clean up unnecessary spaces and path characters."""
    return os.path.basename(filename).replace(".pdf", "").replace(" ", "_")


def process_pdf(pdf_path, media_save_dir):
    """Extract text, images and tables from PDFs using PyMUPDF. LangChain's "document" awaits."""
    base_filename = sanitize_filename(pdf_path)
    source_file_name = os.path.basename(pdf_path)
    print(f"\n--- '{base_filename}' 파일 처리 시작 ---")

    doc = None
    all_docs = []

    # 폴더가 없으면 생성
    if not os.path.exists(media_save_dir):
        os.makedirs(media_save_dir)
        print(f"폴더 생성 완료: '{media_save_dir}'")

    try:
        doc = fitz.open(pdf_path)
        print(f"-> 총 {len(doc)} 페이지의 문서를 열었습니다.")

        for i, page in enumerate(doc):
            page_num = i + 1
            print(f"\n== {page_num} 페이지 처리 중... ==")

            # 텍스트 추출
            text = page.get_text()
            if text:
                print(f"-> {len(text)} 자의 텍스트 추출.")
                all_docs.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": source_file_name,
                            "page": page_num,
                            "type": "text",
                        },
                    )
                )

            # 이미지 추출
            image_list = page.get_images()

            if image_list:
                print(f"-> {len(image_list)} 개의 이미지 발견.")

                for img_index, img_info in enumerate(image_list):
                    xref = img_info[0]

                    try:
                        # doc에서 실제 이미지 데이터 추출
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]

                        image_filename = f"{base_filename}_page_{page_num}_img_{img_index}.{image_ext}"
                        image_save_path = os.path.join(media_save_dir, image_filename)

                        with open(image_save_path, "wb") as f:
                            f.write(image_bytes)

                        # 이미지 Document 생성
                        all_docs.append(
                            Document(
                                page_content=f"{source_file_name} {page_num} 페이지의 이미지 (인덱스 {img_index})",
                                metadata={
                                    "source": source_file_name,
                                    "page": page_num,
                                    "type": "image",
                                    "path": image_save_path,
                                },
                            )
                        )
                        print(f"-> 이미지 저장 및 문서 생성: {image_save_path}")

                    except Exception as e:
                        print(f"[경고] 이미지(xref= {xref}) 처리 실패: {e}")
                        continue  # 다음 이미지로 넘어감

            # 표(Table) 추출
            found_tables = page.find_tables()
            if found_tables.tables:
                print(f"-> {len(found_tables.tables)} 개의 표 발견.")
                for table_index, table in enumerate(found_tables.tables):
                    try:
                        clip_area = table.bbox  # 표의 영역
                        pix = page.get_pixmap(clip=clip_area)

                        table_filename = (
                            f"{base_filename}_page_{page_num}_table_{table_index}.png"
                        )
                        table_save_path = os.path.join(media_save_dir, table_filename)
                        pix.save(table_save_path)

                        # 표(Table) Document 생성
                        all_docs.append(
                            Document(
                                page_content=f"{source_file_name} {page_num} 페이지의 표(Table) (인덱스 {table_index})",
                                metadata={
                                    "source": source_file_name,
                                    "page": page_num,
                                    "type": "table",
                                    "path": table_save_path,
                                },
                            )
                        )
                        print(f"-> 표(Table) 저장 및 문서 생성: {table_save_path}")
                    except Exception as e:
                        print(f"[경고] 표(Table) 처리 실패: {e}")

    except Exception as e:
        print(f"[오류] PDF 파일을 여는 중 문제가 발생했습니다.: {e}")
        return []

    finally:
        # 작업 완료 후 PDF 문서 닫기
        if doc:
            doc.close()

    print(f"--- '{base_filename}' 파일 처리 완료 ---")
    return all_docs  # 성공 시 처리된 데이터 반환


# LangChain으로 분할 및 벡터화
def vectorize_documents(all_docs, db_path):
    """Recieve a list of documents, split the text, and store it in ChromaDB"""
    if not all_docs:
        print("[오류] 벡터화 할 문서가 없습니다.")
        return

    text_docs = [doc for doc in all_docs if doc.metadata["type"] == "text"]
    media_docs = [doc for doc in all_docs if doc.metadata["type"] in ["image", "table"]]

    # 텍스트 분할
    print(f"\n--- 텍스트 분할 시작 ({len(text_docs)} 개) ---")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, separators=["\n\n", "\n", " ", ""]
    )
    text_chunks = text_splitter.split_documents(text_docs)
    print(f"-> 텍스트 청크 생성 완료: {len(text_chunks)} 개")

    # 미디어 문서와 통합
    final_documents = text_chunks + media_docs

    # ChromaDB에 저장
    print(f"\n--- 총 {len(final_documents)} 개의 문서를 벡터 DB에 저장합니다. ---")

    # OpenAI API 키가 있는 지 확인
    if not os.getenv("OPENAI_API_KEY"):
        print("[오류] .env 파일에 OPENAI_API_KEY가 설정되지 않았습니다.")
        return

    embedding = OpenAIEmbeddings(model="text-embedding-3-small")

    # DB가 이미 있다면 삭제 (테스트를 위해 매번 새로 생성)
    if os.path.exists(db_path):
        print(f"기존 DB({db_path})를 삭제합니다.")
        import shutil

        shutil.rmtree(db_path)

    vectorstore = Chroma.from_documents(
        documents=final_documents, embedding=embedding, persist_directory=db_path
    )

    print(f"벡터 DB 저장 완료! (경로: {db_path})")
    return vectorstore


# 메인 실행
if __name__ == "__main__":
    TEST_PDF_FILE = "FAQ.pdf"
    full_pdf_path = os.path.join(PDF_SOURCE_DIR, TEST_PDF_FILE)

    # 테스트용 PDF 파일이 있는 지 확인
    if not os.path.exists(full_pdf_path):
        print(f"[시작 오류] 테스트 할 PDF 파일을 찾을 수 없습니다. '{full_pdf_path}'")
        print(f"'{PDF_SOURCE_DIR}' 폴더에 PDF 파일을 넣어주세요.")
    else:
        # 1단계 실행: PDF 처리
        documents = process_pdf(pdf_path=full_pdf_path, media_save_dir=MEDIA_SAVE_PATH)

        if documents:
            vectorize_documents(documents, DB_PATH)

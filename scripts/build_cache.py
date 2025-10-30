# import os
# import sqlite3
# import time
# from dotenv import load_dotenv

# from langchain_core.documents import Document
# from langchain_openai import OpenAIEmbeddings

# # from langchain_chroma import Chroma
# from langchain_postgres import PGVector

# from rag_core import LOG_DB_PATH, setup_database
# from organization_tools import refine_qa_for_cache

# load_dotenv()

# # CACHE_DB_PATH = os.paht.join(BASE_DIR, "vectorstore/chromadb_cache")
# DATABASE_URL = os.getenv("DATABASE_URL")


# def run_cache_builder():
#     """
#     Read the raw logs from 'chat_logs.db', verify them with LLM (refine_qa_for_cache), and then store them in 'Semantic DB' (chromadb_cache).
#     """
#     print("--- [Cache Builder] 작업 시작 ---")
#     start_time = time.time()

#     if not os.getenv("OPENAI_API_KEY"):
#         print("[오류] .env 파일에 OPENAI_API_KEY가 없습니다. 작업을 중단합니다.")
#         return

#     # DB 연결 및 라벨링 컬럼 확인
#     # setup_database()를 호출하여 processed_for_cache 컬럼이 있는 지 확인/추가
#     try:
#         print(f"-> '{LOG_DB_PATH}' DB 연결 및 스키마 확인...")
#         setup_database()
#         conn = sqlite3.connect(LOG_DB_PATH, timeout=10)
#         conn.row_factory = sqlite3.Row
#         cursor = conn.cursor()
#     except Exception as e:
#         print(f"[오류] 로그 유({LOG_DB_PATH}) 연결 실패: {e}")
#         return

#     # 필터링: 정제할 후보 로그 선택
#     try:
#         cursor.execute(
#             """
#             SELECT id, question, answer FROM chat_logs 
#             WHERE processed_for_cache = 0 
#               AND satisfaction = 1
#               AND route IN ('rag', 'counseling')
#             """
#         )
#         candidate_logs = cursor.fetchall()
#     except Exception as e:
#         print(f"[오류] 후보 로그 선택 실패: {e}")
#         conn.close()
#         return

#     if not candidate_logs:
#         print(
#             "-> [결과] 정제할 신규 로그(satisfaction= 1)가 없습니다. 작업을 종료합니다."
#         )
#         conn.close()
#         return

#     print(f"-> [필터링 완료] 총 {len(candidate_logs)} 개의 후보 로그 발견.")

#     # 의미 분석(LLM)
#     print(f"-> [LLM 정제 시작] 후보 로그를 refine_qa_for_cache 도구로 검증합니다...")

#     final_docs_to_cache = []
#     processed_ids = []

#     for log in candidate_logs:
#         log_id = log["id"]
#         question = log["question"]
#         answer = log["answer"]

#         # organization_tools 정제 도구 호출
#         # 토큰 비용 발생 지점
#         refined_answer = refine_qa_for_cache(question=question, answer=answer)

#         if "REJECT" in refined_answer:
#             print(f"    - (ID: {log_id} REJECT. (사유: 장난/중복/불완전)>")
#             # REJECT 된 로그도 처리 완료로 라벨링 하여 다시 검사하지 않음
#             processed_ids.append(log_id)
#         else:
#             print(f"    + (ID: {log_id} APPROVE. 캐시 DB에 저장합니다.")
#             # semantic DB에 저장할 Document 객체 생성
#             doc = Document(
#                 page_content=question,
#                 metadata={"answer": refined_answer, "source_log_id": log_id},
#             )
#             final_docs_to_cache.append(doc)
#             processed_ids.append(log_id)

#     # [저장] Semantic DB (Chroma)에 최종 문서 저장
#     if final_docs_to_cache:
#         try:
#             cache_collection_name = "semantic_cache"
#             print(
#                 f"-> [저장] 총 {len(final_docs_to_cache)} 개의 정제된 문서를 PGVector'{cache_collection_name}'에 저장합니다."
#             )
#             embedding = OpenAIEmbeddings(model="text-embedding-3-small")

#             # Chroma DB가 이미 있어도 .add_documents()로 추가
#             vectorstore = PGVector(
#                 connection=DATABASE_URL,
#                 embedding_function=embedding,
#                 collection_name=cache_collection_name,
#             )
#             vectorstore.add_documents(final_docs_to_cache)
#             print(f"->  'Semantic DB' 저장 완료")
#         except Exception as e:
#             print(f"[오류] Semantic DB 저장 실패: {e}")
#             # DB 저장에 실패하면 라벨링도 건너뛰어 다음 실행 시 재시도
#             conn.close()
#             return
#     else:
#         print(f"-> [저장] LLM 정제 결과, 캐시에 저장할 유효한 문서가 없습니다.")

#     # [라벨링] 원본 로그 processed_for_cache= 1로 업데이트
#     if processed_ids:
#         try:
#             print(
#                 f"-> [라벨링] 처리 완료된 {len(processed_ids)} 개의 로그를 processed_for_cache= 1로 업데이트합니다."
#             )
#             # executemany를 사용하여 여러 ID를 한 번에 업데이트
#             cursor.executemany(
#                 "UPDATE chat_logs SET processed_for_cache= 1 WHERE id = ?",
#                 [(pid,) for pid in processed_ids],
#             )
#             conn.commit()
#             print(f"->      라벨링 완료.")
#         except Exception as e:
#             print(f"[오류] 라벨링 (DB_UPDATE) 실패: {e}")

#     conn.close()
#     end_time = time.time()
#     print(
#         f"--- [Cache Builder] 작업 완료 (총 소요 시간: {end_time - start_time:.2f} 초) ---"
#     )


# if __name__ == "__main__":
#     run_cache_builder()

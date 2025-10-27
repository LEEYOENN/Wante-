import streamlit as st
import plotly.express as px
import pandas as pd
import sqlite3
import os
import tempfile
from dotenv import load_dotenv

from organization_agent import run_organization_agent
from datetime import datetime

from ingest_vectorize import process_pdf, MEDIA_SAVE_PATH, DB_PATH

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


load_dotenv()

LOG_DB_PATH = "chat_logs.db"

# streamlit 페이지 설정
st.set_page_config(page_title="WanteDash Board For Admin", layout="wide")
st.title("WanteDash Board")
st.markdown("Discord 상담 내역을 확인하고, 지식을 관리합니다.")


# 데이터 로드 함수
@st.cache_data(ttl=10)
def load_data():
    """Loading data from chat_logs.db"""
    if not os.path.exists(LOG_DB_PATH):
        return pd.DataFrame()

    try:
        conn = sqlite3.connect(LOG_DB_PATH, timeout= 10)
        # 'route' 컬럼이 없을 수도 있는 초기 DB 호환
        table_info = pd.read_sql_query("PRAGMA table_info(chat_logs)", conn)
        if "route" not in table_info["name"].values:
            st.warning(
                "Warning: Column 'route' does not exist in log DB. Please run setup_database() in 'rag_core.py'."
            )
            # Load without route column
            df = pd.read_sql_query(
                "SELECT * FROM chat_logs ORDER BY timestamp DESC", conn
            )
            df["route"] = "unknown"  # Add temp route column
        else:
            df = pd.read_sql_query(
                "SELECT * FROM chat_logs ORDER BY timestamp DESC", conn
            )

        conn.close()

        # 날짜/시간 포맷 정리
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception as e:
        st.error(f"로그 DB 로드 실패: {e}")
        return pd.DataFrame()

# Refresh Button
if st.button("데이터 새로고침"):
    st.cache_data.clear()
    st.session_state["rerun_trigger"] = True

df = load_data()

# DASH BOARD UI
if df.empty:
    st.warning(f"아직 저장된 로그가 없습니다. (DB 경로: '{LOG_DB_PATH}')")
else:
    # KPI and Pie chart
    col1, col2 = st.columns([1.5, 1])  # Adjust column ratio
    with col1:
        st.subheader("기본 현황")
        total_queries = len(df)
        dm_queries = df["is_dm"].sum()
        channel_queries = total_queries - dm_queries

        kpi_cols = st.columns(3)
        kpi_cols[0].metric("총 상담 건수", f"{total_queries} 건")
        kpi_cols[1].metric("DM 상담", f"{dm_queries} 건")
        kpi_cols[2].metric("채널 멘션 상담", f"{channel_queries} 건")

    with col2:
        # Proportion by consultation type (pie chart)
        st.subheader("상담 유형별 비중")
             
        if "route" in df.columns and not df["route"].empty:
            route_counts = df["route"].value_counts().reset_index()
            route_counts.columns = ["route", "count"]  # Plotly를 위한 컬럼명 변경
            # 1. Plotly 파이 차트 생성
            fig_pie = px.pie(
                route_counts,
                names="route",  # 'route' 컬럼(rag, counseling)을 파이 조각 이름으로 사용
                values="count",  # 'count' 컬럼(건수)을 파이 조각 크기로 사용
                title="상담 유형",
            )
            # 2. Streamlit에 차트 그리기
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("(Fail to load column 'route')")

    #  with col2:
    #     # Proportion by consultation type (pie chart)
    #     st.subheader("상담 유형별 비중")
    #     if 'route' in df.columns and not df['route'].empty:
    #         # 데이터를 Altair가 읽기 좋은 DataFrame으로 변환
    #         route_counts = df["route"].value_counts().reset_index()
    #         route_counts.columns = ['route', 'count']

    #         # Altair 파이 차트 생성
    #         pie_chart = alt.Chart(route_counts).mark_arc(outerRadius= 120).encode(
    #             # theta가 파이 조각의 크기를 결정
    #             theta = alt.Theta("count: Q", stack= True),
    #             # color가 조각의 색상을 결정
    #             color = alt.Color("route: N"),
    #             # 마우스를 울렸을 때 표시될 정보
    #             tooltip = ["route", "count"]
    #         )
    #         st.altair_chart(pie_chart, use_container_width= True)
    #     else:
    #         st.info("(Fail to load column 'route')")

    st.divider()

    # Daily consultation count chart
    st.subheader("일별 상담 추이")
    daily_counts = df.set_index("timestamp").resample("D").size().rename("상담 건수")
    st.bar_chart(daily_counts)

    # 전체 상담 내역(테이블)
    st.subheader("전체 상담 내역 (최신순)")

    # Display route columns
    display_columns = ["timestamp", "user_name", "is_dm", "route", "question", "answer"]
    # Check once more whether the column to be displayed actually exists in the DB (stability)
    display_columns_exists = [col for col in display_columns if col in df.columns]
    st.dataframe(df[display_columns_exists], use_container_width=True)

    # 확장을 이용해 전체 로그 보기
    with st.expander("전체 원본 데이터 보기 (JSON 포함)"):
        st.dataframe(df)

# Milestone 4 지식 업데이트 기능
st.divider()
st.header("챗봇 지식 관리")
st.markdown("새로운 PDF/CSV 파일을 업로드하여 관련 지식을 업데이트합니다.")

uploaded_file = st.file_uploader("-----", type=["pdf", "csv"])

if uploaded_file is not None:
    st.subheader("아래의 버튼을 눌러 챗봇의 지식을 업데이트합니다.")
    if st.button(f"'{uploaded_file.name}' 업데이트", type="secondary"):
        # API 키가 있는 지 다시 확인
        if not os.getenv("OPENAI_API_KEY"):
            st.error("오류: .env 파일에서 OPENAI_API_KEY를 찾을 수 없습니다.")
        else:
            temp_file_path = None
            final_new_documents = []

            try:
                file_suffix = os.path.splitext(uploaded_file.name)[1]
                # 업로드 된 파일을 임시 파일로 저장
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=file_suffix
                ) as tmpfile:
                    tmpfile.write(uploaded_file.getvalue())
                    temp_file_path = tmpfile.name

                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=200,
                    separators=["\n\n", "\n", " ", ""],
                )

                if uploaded_file.type == "application/pdf":
                    st.info(f"'{uploaded_file.name}' PDF 파일 처리 중...(PyMUPDF)")
                    new_docs_raw = process_pdf(
                        pdf_path=temp_file_path, media_save_dir=MEDIA_SAVE_PATH
                    )
                    text_docs = [
                        doc for doc in new_docs_raw if doc.metadata["type"] == "text"
                    ]
                    media_docs = [
                        doc
                        for doc in new_docs_raw
                        if doc.metadata["type"] in ["image", "table"]
                    ]
                    new_text_chunks = text_splitter.split_documents(text_docs)
                    final_new_documents = new_text_chunks + media_docs
                elif uploaded_file.type == "text/csv":
                    st.info(f"'{uploaded_file.name}' CSV 파일 처리 중... (CSVLoader)")
                    loader = CSVLoader(file_path=temp_file_path, encoding="utf-8-sig")
                    new_docs_raw = loader.load()
                    final_new_documents = text_splitter.split_documents(new_docs_raw)

                # DB에 추가
                if not final_new_documents:
                    st.error("파일에서 처리할 문서를 찾지 못했습니다.")

                else:
                    st.info(
                        f"{len(final_new_documents)} 개의 새 문서를 벡터 DB에 추가합니다."
                    )
                    # 기존 DB 로드
                    embedding = OpenAIEmbeddings(model="text-embedding-3-small")
                    vectorstore = Chroma(
                        persist_directory=DB_PATH, embedding_function=embedding
                    )
                    # [핵심] .add_documents() 매서드 사용
                    vectorstore.add_documents(final_new_documents)

                    st.success(
                        f"'{uploaded_file.name}' 의 문서 {len(final_new_documents)} 개가 DB에 성공적으로 추가 되었습니다."
                    )
                    st.balloons()
                    # 캐시 초기화
                    st.cache_data.clear()
            except Exception as e:
                st.error(f"파일 처리 중 오류 발생: {e}")
            finally:
                # 임시 파일 삭제
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

# Organization AI Agent : create a Report
st.divider()
st.header("Organization AI Agent (보고서 생성)")

today = datetime.now().strftime('%Y-%m-%d')
report_filename = f"{today}_weekly_report.md"
report_task = f"""
'chat_logs.db'에서 최근 7일간의 모든 로그를 가져와서,
트렌드를 분석하고,
그 결과를 '{report_filename}' 파일 이름으로 저장해줘..
"""

# Report save path
REPORT_SAVE_PATH = "reports"
report_file_path = os.path.join(REPORT_SAVE_PATH, report_filename)

st.subheader("주간 상담 리포트 (최근 7일)")
st.markdown(f"생성될 파일명: '{report_file_path}'")
st.text_area("에이전트 작업 목표:", report_task, height= 150, disabled= True)

# Create Report Button
if st.button("주간 리포트 생성 시작", type= "primary"):
    if run_organization_agent is None:
        st.error("에이전트 실행 함수를 로드하지 못했습니다.")
    else:
        # Run Agent
        with st.spinner(f"'Organization ai agent'가 로그를 분석하고 리포트를 작성 중입니다... (최대 1 ~ 2분 소요)"):
            try:
                final_agent_message = run_organization_agent(
                    task_prompt= report_task,
                    thread_id= f"streamlit_report_{today}"
                )
                st.success("에이전트 작업 완료!")
                st.text_area("에이전트 최종 응답:", final_agent_message, height= 100)

                # 리포트 파일 확인 및 다운로드 버튼 제공
                if os.path.exists(report_file_path):
                    st.info(f"'{report_file_path}'에서 생성된 파일을 찾았습니다.")

                    with open(report_file_path, "r", encoding= "utf-8") as f:
                        report_content = f.read()

                    with st.expander("생성된 리포트 미리보기 (Markdown)"):
                        st.markdown(report_content)

                    st.download_button(
                        label= "생성된 리포트(.md) 다운로드",
                        data= report_content,
                        file_name= report_filename,
                        mime= "text/markdown"
                    )
                else:
                    st.error(f"에이전트가 리포트 파일을 생성하지 못했습니다. (경로: {report_file_path})")

            except Exception as e:
                st.error(f"리포트 생성 중 오류 발생: {e}")
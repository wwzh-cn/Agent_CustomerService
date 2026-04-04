import os
# os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'  # 解决OpenMP库冲突问题
# # 设置huggingface镜像和超时
# os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'  # 使用国内镜像
# os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '300'  # 设置huggingface下载超时300秒
# os.environ['HF_HUB_CONNECT_TIMEOUT'] = '60'    # 设置连接超时60秒
# # os.environ['TRANSFORMERS_OFFLINE'] = '1'       # 离线模式，不使用网络
# os.environ['HF_HUB_OFFLINE'] = '1'             # huggingface hub离线模式

import time
import uuid

import streamlit as st
from agent.react_agent import ReactAgent

# 标题
st.title("智扫通机器人智能客服")
st.divider()

if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()

if "session_id" not in st.session_state:
    # 生成唯一的会话ID
    st.session_state["session_id"] = f"streamlit_session_{uuid.uuid4().hex[:8]}"

if "message" not in st.session_state:
    st.session_state["message"] = []

for message in st.session_state["message"]:
    st.chat_message(message["role"]).write(message["content"])

# 用户输入提示词
prompt = st.chat_input()

if prompt:
    st.chat_message("user").write(prompt)
    st.session_state["message"].append({"role": "user", "content": prompt})

    response_messages = []
    with st.spinner("智能客服思考中..."):
        res_stream = st.session_state["agent"].execute_stream(
            prompt, session_id=st.session_state["session_id"]
        )

        def capture(generator, cache_list):

            for chunk in generator:
                cache_list.append(chunk)

                for char in chunk:
                    time.sleep(0.01)
                    yield char

        st.chat_message("assistant").write_stream(capture(res_stream, response_messages))
        st.session_state["message"].append({"role": "assistant", "content": response_messages[-1]})
        st.rerun()



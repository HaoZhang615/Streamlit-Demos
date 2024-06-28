from openai import AzureOpenAI
import streamlit as st

st.title("基于自有数据的 Azure OpenAI")

# Initialize session state attributes  
if "messages" not in st.session_state:  
    st.session_state.messages = []  

# function to use Azure AI Search to built RAG pattern for QA on the files
def aoai_on_your_data(query,file_name):
    endpoint = st.secrets["GPT4O_API_ENDPOINT"]
    key = st.secrets["GPT4O_API_KEY"]
    deployment = st.secrets["GPT4O_MODEL_NAME"]
    embedding_deployment = st.secrets["GPT40_API_EMBEDDING_MODEL_NAME"]
    search_endpoint = st.secrets["AZURE_AI_SEARCH_SERVICE_ENDPOINT"]
    search_key = st.secrets["AZURE_AI_SEARCH_ADMIN_KEY"]
    search_index = st.secrets["AZURE_AI_SEARCH_INDEX_NAME_ABB"]

    client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key = key,
    api_version="2024-02-01",
    )

    completion = client.chat.completions.create(
    model=deployment,
    temperature=0.0,
    messages=[
        {
            "role": "user",
            "content": query,
        }
    ],
    extra_body={
        "data_sources": [
            {
                "type": "azure_search",
                "parameters": {
                    "endpoint": search_endpoint,
                    "index_name": search_index,
                    "authentication": {
                        "type": "api_key",
                        "key": search_key
                    },
                "query_type": "vector_semantic_hybrid",
                "embedding_dependency": {
                    "deployment_name": embedding_deployment,
                    "type": "deployment_name"
                },
                "role_information":"""
                You are a helpful assistant that helps the user with their request. 
                You extract key entity from user's request and search for the relevant information in the data source.
                You always reply in Chinese language as the user request and you answer very briefly without giving sources.
                """,
                "semantic_configuration":"abbchinael-semantic-configuration",
                "top_n_documents": 5,
                "filter": f"title eq '{file_name}.pdf'"

                }
            }
        ]
    }
)
    return completion.choices[0].message.content

# Sidebar Configuration
with st.sidebar:
    # Temperature and token slider
    temperature = st.sidebar.slider(
        "模型温度",
        min_value=0.0,
        max_value=1.0,
        value=0.5,
        step=0.1
    )
    Max_Token = st.sidebar.slider(
        "最大token限制",
        min_value=10,
        max_value=120000,
        value=256,
        step=64
    )
    File_Name = st.selectbox("选择问答文档", 
                           ["A", 
                            "B",
                            "C",
                            "D",
                            "E",
                            "F",
                            "G",
                            "H",
                            "I",
                            "J",
                            "K",
                            "L",
                            "M",
                            "N",
                            "O",
                            "P",
                            "Q",
                            "R",
                            "S",
                            "T",
                            "U",
                            "V",
                            "W",
                            "X",
                            "Y",
                            "Z",
                            "Z1",
                            "Z2",
                            "Z3",
                            "Z4",
                            "Z5",
                            "Z6",
                            "Z7",
                            "Z8",
                            "Z9",
                            "Z10",
                            "Z11",
                            "Z12",
                            "Z13",
                            "Z14",
                            "Z15",
                            "Z16",
                            "Z17",
                            "Z18",
                            "Z19",
                            "Z20",
                            "Z21",
                            "Z22",
                            "Z23",
                            "Z24"], index=0)
    Parameter_Name = st.selectbox("选择目标参数", 
                           ["系统电压（标称电压)", 
                            "额定频率",
                            "额定电流",
                            "海拔高度",
                            "环境温度",
                            "额定短时耐受电流（热稳定电流）",
                            "额定峰值耐受电流（动稳定电流）",
                            "复合绝缘外壳 (开关柜)防护等级",
                            "钢板厚度",
                            "镀银需求",
                            "智能化要求",
                            "包装要求",
                            "开关柜颜色要求",
                            "泄压通道要求",
                            "弧光保护的要求",
                            "多功能表计的要求",
                            "综合保护/继电保护/微机保护的要求",
                            "质保期的要求",
                            "是否有容性负载",
                            "是否有电缆室照明的要求",
                            "二次回路的控制电压要求",
                            "计量表是否要求第三方检测"], index=0)
    with st.form("prompt_form"):
        init_prompt = st.selectbox(
            '提问示例...',
            [f"请寻找以下参数: {Parameter_Name}"]
        )
        submit_button = st.form_submit_button(label='提交问题')

    def clear_chat_history():
        st.session_state.messages = []
        st.session_state.chat_history = []
    if st.button("重新开始对话 :arrows_counterclockwise:"):
        clear_chat_history()
  

for message in st.session_state.messages:  
    with st.chat_message(message["role"]):  
        st.markdown(message["content"])  
  
# Handle new message  
if prompt := st.chat_input(f"请寻找以下参数: {Parameter_Name}"):
    # Display chat history  
    st.session_state.messages.append({"role": "user", "content": prompt})  
    with st.chat_message("user"):  
        st.markdown(prompt)  
    with st.chat_message("assistant"): 
        st.markdown(aoai_on_your_data(prompt,File_Name))
    st.session_state.messages.append({"role": "assistant", "content": aoai_on_your_data(prompt,File_Name)})  
if submit_button:
    # Display chat history
    st.session_state.messages.append({"role": "user", "content": init_prompt})
    with st.chat_message("user"):
        st.markdown(init_prompt)
    with st.chat_message("assistant"):
        st.markdown(aoai_on_your_data(init_prompt, File_Name))
    st.session_state.messages.append({"role": "assistant", "content": aoai_on_your_data(init_prompt, File_Name)})

import asyncio
from datetime import datetime, timezone
import uuid
from fastapi import Depends
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.schemas.chunk_dto import ChunkDTO
from src.db.pg_db import get_db
from src.services.chunk_service import ChunkService
from src.utils.logger import get_logger
logger = get_logger(__name__)

# 【改造项：分块策略】评测线 A7 的第 4 项改造，开关式，置 False 即回到原始行为。
# 背景见 评测/README.md「第 4 项改造」——原始配置下 12% 的 chunk 是低质碎片，
# 其中「词被从中间切断」那一类会让信息永久召不回（评测集 F14 是实证）。
SMART_CHUNKING = True    # 中文标点 separators + 短块合并
MIN_CHUNK_CHARS = 120    # 短于此字数的块合并回前一块


class PartitionHandler:    
    def __init__(self):
        pass

    async def file_partition(self, file_id, file_name,file_path,file_extension):
        try:
            logger.info(f"分割 fileId={file_id},路径={file_path} to chunk")
            if file_extension == ".docx":
                loader = Docx2txtLoader(file_path)
            elif file_extension == ".pdf":
                loader = PyPDFLoader(file_path)
            elif file_extension == ".txt":
                loader = TextLoader(file_path, encoding="utf-8")

            docs = loader.load()

            # Split
            # 创建文本分割器实例
            #
            # 【改造项：分块策略】开关，False = 回到原始行为。
            # 原始 separators 是英文导向的 ["\n\n", "\n", " ", ""]。中文文本里
            # " " 极少出现，所以一旦 \n\n / \n 切不动，就只剩「按字符硬切」一条路 ——
            # 实测它把 `王浆酸(10 - HDA)` 从中间劈成两块，前半留在块尾、后半成了碎片块，
            # 而碎片块语义残缺、几乎永远召不回，**信息等于永久丢失**（评测集 F14 因此答不出）。
            # 加中文标点后，切点落在句子边界而不是词中间。
            if SMART_CHUNKING:
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=300,
                    chunk_overlap=50,
                    length_function=len,
                    separators=["\n\n", "\n", "。", "！", "？", "；", "，", "、", " ", ""],
                )
            else:
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=300,          # 每个块的最大字符数 值为300最佳
                    chunk_overlap=50,        # 相邻块之间的重叠字符数 值为50最佳
                    length_function=len,     # 计算文本长度的函数
                    # add_start_index=True,    # 是否添加起始索引
                )

            # Make splits
            split_docs = text_splitter.split_documents(docs)

            # 【改造项：分块策略】合并过短块。
            # 分块器对「段落短而多」的文本会产出大量 < 120 字的碎片块 ——
            # 实测原始配置下 83 段里有 10 段（12%），其中一半是 overlap 造出来的
            # 冗余块（内容几乎是前一块尾巴的重复，白占一个检索位），另一半是语义
            # 残缺的真碎片（开头就是半句话，向量检索几乎召不回）。
            # 这里把短块并回前一块，保证每块都有完整语义。
            if SMART_CHUNKING:
                merged: list = []
                for d in split_docs:
                    if merged and len(d.page_content) < MIN_CHUNK_CHARS:
                        merged[-1].page_content += "\n" + d.page_content
                    else:
                        merged.append(d)
                if len(merged) != len(split_docs):
                    logger.info(f"短块合并：{len(split_docs)} -> {len(merged)} 段"
                                f"（阈值 {MIN_CHUNK_CHARS} 字）")
                split_docs = merged
            
            chunks_to_insert = []
            for i, doc in enumerate(split_docs):
                chunk_dto = ChunkDTO(
                    uuid=uuid.uuid1(),
                    file_id=file_id,
                    file_name=file_name,
                    context=doc.page_content,
                    index=i,
                    status=0,
                    create_time=datetime.now(timezone.utc)
                )
                chunks_to_insert.append(chunk_dto)
            
             # 分批次批量插入
            batch_size = 1000  # 每批插入的记录数
            total_chunks = len(chunks_to_insert)
            success_count = 0
            
            async for db in get_db():
                chunk_service = ChunkService(db)

                for i in range(0, total_chunks, batch_size):
                    batch = chunks_to_insert[i:i + batch_size]
                    batch_num = i // batch_size + 1
                    total_batches = (total_chunks + batch_size - 1) // batch_size
                    # logger.info(f"分割文件 {file_id} 第 {i+1} 个chunk,context:{doc.page_content}")
                    try:
                        await chunk_service.batch_create(batch)
                        success_count += len(batch)
                        logger.info(f"批次 {batch_num}/{total_batches} 插入成功，"
                                  f"本批 {len(batch)} 条，累计 {success_count}/{total_chunks} 条")
                        
                        # 添加短暂延迟避免数据库压力过大
                        await asyncio.sleep(0.1)

                    except Exception as e:
                        logger.error(f"批次 {batch_num} 插入失败: {e}")
                        import traceback
                        traceback.print_exc()
                        
                logger.info(f"文件 {file_name} 分割完成，总共插入 {success_count}/{total_chunks} 个 chunks")

        except FileNotFoundError:
            print(f"文件 {file_path} 未找到。")
            return None
        except Exception as e:
            print(f"读取文件时发生错误: {e}")
            return None

    
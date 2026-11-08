"""
向量检索服务
基于Chroma实现题目相似度检索
两层检索：第一层简单匹配（初筛），第二层向量检索（精筛）
"""
import os
import sys
from typing import List, Dict

# 添加项目根目录到path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


class VectorSearchService:
    """
    向量检索服务
    使用Chroma作为向量数据库，支持题目相似度检索
    """

    def __init__(self):
        self.chroma_path = settings.CHROMA_DB_PATH
        self.collection_name = "exam_questions"
        self.chroma_client = None
        self.collection = None
        self._init_chroma()

    def _init_chroma(self):
        """初始化Chroma客户端"""
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            os.makedirs(self.chroma_path, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(
                path=self.chroma_path,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "历年真题题目向量库"}
            )
            print(f"Chroma initialized at {self.chroma_path}")
        except ImportError:
            print("Warning: chromadb not installed, vector search will use simple match only")
            self.chroma_client = None
            self.collection = None

    def index_questions(self, questions: List[Dict], mode: str = "replace") -> int:
        """
        将题目索引到向量库。每个知识标签生成一个独立向量。
        questions: [{"exam_id": "...", "content": "...", "knowledge_points": [...], ...}]
        mode: "replace" — clear collection and rebuild; "append" — add to existing
        返回: 成功索引的向量数量（= Σ knowledge_points）
        """
        if not self.collection:
            print("Warning: Chroma not available, skipping indexing")
            return 0

        if not questions:
            return 0

        # Check dimension mismatch — only recreate if actual mismatch
        try:
            existing = self.collection.get(limit=1)
            if existing and existing.get("embeddings") and existing["embeddings"]:
                existing_dim = len(existing["embeddings"][0])
                sample_text = self._build_embed_text(
                    kp_name=questions[0].get("knowledge_points", ["测试"])[0],
                    question_type=questions[0].get("question_type", ""),
                    difficulty=questions[0].get("difficulty", "medium"),
                    source=questions[0].get("source", ""),
                    year=questions[0].get("year", 0),
                    question_number=questions[0].get("question_number", ""),
                    content=questions[0].get("content", ""),
                    answer=questions[0].get("answer", ""),
                )
                sample_embedding = self._get_embedding(sample_text)
                if len(sample_embedding) != existing_dim:
                    print(f"Dimension mismatch: old={existing_dim} new={len(sample_embedding)}, recreating collection")
                    self.chroma_client.delete_collection(self.collection.name)
                    self.collection = self.chroma_client.create_collection(
                        name="exam_questions",
                        metadata={"hnsw:space": "cosine"}
                    )
        except Exception:
            pass

        # Clear old data in replace mode
        if mode != "append":
            try:
                existing_ids = self.collection.get().get("ids", [])
                if existing_ids:
                    self.collection.delete(ids=existing_ids)
            except Exception:
                pass

        # Generate embeddings: one vector per knowledge_point
        ids = []
        embeddings = []
        metadatas = []

        for q in questions:
            exam_id = q.get("exam_id", "")
            content = q.get("content", "")
            knowledge_points = q.get("knowledge_points", [])
            difficulty = q.get("difficulty", "medium")
            source = q.get("source", "")
            year = q.get("year", 0)
            region = q.get("region", "")
            question_type = q.get("question_type", "")
            question_number = q.get("question_number", "")
            answer = q.get("answer", "")

            for kp_idx, kp_name in enumerate(knowledge_points):
                embed_text = self._build_embed_text(
                    kp_name, question_type, difficulty,
                    source, year, question_number, content, answer
                )
                embedding = self._get_embedding(embed_text)

                chunk_id = f"{exam_id}::kp-{kp_idx}"
                ids.append(chunk_id)
                embeddings.append(embedding)
                metadatas.append({
                    "exam_id": exam_id,
                    "kp_index": kp_idx,
                    "kp_name": kp_name,
                    "source": source,
                    "year": year,
                    "region": region,
                    "difficulty": difficulty,
                    "question_number": question_number,
                    "knowledge_points": ",".join(knowledge_points) if knowledge_points else "",
                    "content_preview": content[:200],
                })

        # Batch add
        if ids:
            self.collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas)

        return len(ids)

    def _build_embed_text(self, kp_name: str, question_type: str, difficulty: str,
                          source: str, year: int, question_number: str,
                          content: str, answer: str) -> str:
        """Build embedding text with knowledge point as the primary signal."""
        return (
            f"考点：{kp_name}。"
            f"题型：{question_type}。"
            f"难度：{difficulty}。"
            f"来源：{source} {year}年第{question_number}题。"
            f"题目：{content[:500]}。"
            f"答案：{answer}"
        )

    def search_similar(
        self,
        query_text: str,
        knowledge_points: List[str],
        difficulty: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        搜索相似题目（两层检索）
        1. 第一层：简单匹配（知识点重叠度）
        2. 第二层：向量检索（精筛）

        返回: [{"exam_id": "...", "source": "...", "similarity": 0.85, "match_method": "vector"}, ...]
        """
        if not self.collection:
            return []

        # 获取所有已索引的题目
        all_data = self.collection.get()
        if not all_data or not all_data.get("ids"):
            return []

        # 第一层：简单匹配筛选候选题
        candidate_ids = self._simple_match(knowledge_points, difficulty, all_data)

        # 第二层：向量检索精筛
        query_embedding = self._get_embedding(query_text)

        if candidate_ids:
            # 有候选时：全量向量检索后按候选 id 过滤（chromadb 0.4.x 的 query()
            # 不支持 ids 参数限定子集，where 又只过滤 metadata，故客户端过滤）
            candidate_set = set(candidate_ids)
            n_results = len(all_data.get("ids", []))
        else:
            # 无候选（自由文本搜索或无匹配知识点）：全量向量搜索
            candidate_set = None
            n_results = min(limit * 2, len(all_data.get("ids", [])))

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
            )
        except Exception as e:
            print(f"Vector search error: {e}")
            if not candidate_ids:
                return []
            # 降级到简单匹配结果
            return self._simple_match_results(candidate_ids[:limit], all_data, "simple")

        # 整理结果
        similar_questions = []
        for i, (id, dist) in enumerate(zip(results["ids"][0], results["distances"][0])):
            if candidate_set is not None and id not in candidate_set:
                continue
            metadata = results["metadatas"][0][i]
            similarity = 1 - dist if dist else 0.5

            similar_questions.append({
                "exam_id": id,
                "kp_name": metadata.get("kp_name", ""),
                "source": metadata.get("source", ""),
                "year": metadata.get("year", 0),
                "region": metadata.get("region", ""),
                "knowledge_points": metadata.get("knowledge_points", "").split(","),
                "similarity": round(similarity, 3),
                "match_method": "vector"
            })

        # 按相似度排序
        similar_questions.sort(key=lambda x: x["similarity"], reverse=True)

        return similar_questions[:limit]

    def _simple_match(
        self,
        knowledge_points: List[str],
        difficulty: str,
        all_data: Dict = None
    ) -> List[str]:
        """
        简单匹配筛选候选（第一层）
        基于知识点重叠度快速筛选
        """
        if all_data is None:
            if not self.collection:
                return []
            all_data = self.collection.get()

        if not all_data or not all_data.get("ids"):
            return []

        candidates = []
        kp_set = set(knowledge_points)

        for i, metadata in enumerate(all_data["metadatas"]):
            q_kps = set(metadata.get("knowledge_points", "").split(","))
            kp_name = metadata.get("kp_name", "")
            # Score: exact kp_name match gets bonus weight
            overlap = len(kp_set & q_kps)
            if kp_name and kp_name in kp_set:
                overlap += 2  # bonus for matching the specific chunk's kp

            if overlap > 0:
                # 难度匹配优先
                if metadata.get("difficulty") == difficulty:
                    candidates.append((all_data["ids"][i], overlap, True))
                else:
                    candidates.append((all_data["ids"][i], overlap, False))

        # 排序：先按匹配度，再按难度匹配
        candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)

        return [c[0] for c in candidates[:20]]  # 返回top20候选

    def _simple_match_results(
        self,
        exam_ids: List[str],
        all_data: Dict,
        method: str
    ) -> List[Dict]:
        """将简单匹配结果转换为标准格式"""
        id_to_metadata = {i: m for i, m in zip(all_data["ids"], all_data["metadatas"])}

        results = []
        for exam_id in exam_ids:
            if exam_id in id_to_metadata:
                metadata = id_to_metadata[exam_id]
                results.append({
                    "exam_id": exam_id,
                    "source": metadata.get("source", ""),
                    "year": metadata.get("year", 0),
                    "region": metadata.get("region", ""),
                    "knowledge_points": metadata.get("knowledge_points", "").split(","),
                    "similarity": 0.5,  # 简单匹配不给具体相似度
                    "match_method": method
                })

        return results

    def _get_embedding(self, text: str) -> List[float]:
        """获取文本向量 — dashscope text-embedding-v3 (1024维)"""
        try:
            import os
            import dashscope
            from dashscope import TextEmbedding

            # Ensure API key is set (dashscope doesn't auto-read env)
            if not dashscope.api_key:
                from dotenv import load_dotenv
                load_dotenv()
                dashscope.api_key = os.getenv("DASHSCOPE_API_KEY", "")

            resp = TextEmbedding.call(
                model=TextEmbedding.Models.text_embedding_v3,
                input=text[:2048],
            )
            if resp.status_code == 200 and resp.output and resp.output.get("embeddings"):
                return resp.output["embeddings"][0]["embedding"]
        except Exception as e:
            print(f"dashscope embedding failed: {e}, falling back to pseudo")

        return self._pseudo_embedding(text)

    def _pseudo_embedding(self, text: str) -> List[float]:
        """
        生成伪向量（基于文本哈希）
        仅用于测试，生产环境应使用真实embedding API
        """
        import hashlib

        # 使用固定维度的向量
        dim = 1024
        vector = [0.0] * dim

        # 用文本的hash来填充向量（确保相同文本产生相同向量）
        text_hash = hashlib.md5(text.encode()).digest()

        for i, byte in enumerate(text_hash):
            idx1 = i % dim
            idx2 = (i * 7) % dim
            vector[idx1] += (byte / 255.0 - 0.5) * 0.1
            vector[idx2] += ((byte * 13) % 255 / 255.0 - 0.5) * 0.1

        # L2归一化
        import math
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector

    def build_index_from_exam_bank(self, force: bool = False):
        """从exam_bank构建向量索引。如果索引已存在且维度匹配则跳过。"""
        from app.services.exam_bank import exam_bank_service

        # Skip rebuild if index already populated and dimensions match
        if not force:
            try:
                # chroma get() 默认 include 不含 embeddings（只有 documents/metadatas），
                # 必须显式 include，否则本检查永远失败 → 每次启动全量重建 →
                # 48 次 dashscope 嵌入 API 调用阻塞启动 ~50 秒（2026-08 修复）
                existing = self.collection.get(limit=1, include=["embeddings"])
                if existing and existing.get("ids") and existing.get("embeddings"):
                    existing_dim = len(existing["embeddings"][0])
                    # Quick dimension check with pseudo embedding (no API call)
                    sample_dim = len(self._pseudo_embedding("test"))
                    if existing_dim >= sample_dim * 0.8:  # dimension roughly matches
                        existing_count = self.collection.count()
                        # Expected: Σ knowledge_points across all questions (one vector per kp)
                        expected_count = sum(
                            len(q.knowledge_points)
                            for q in exam_bank_service.questions
                            if q.knowledge_points
                        )
                        if existing_count >= expected_count * 0.9:
                            print(f"Vector index up to date ({existing_count} questions), skipping rebuild")
                            return existing_count
            except Exception:
                pass

        questions_for_index = []
        for q in exam_bank_service.questions:
            if not q.knowledge_points:
                continue

            questions_for_index.append({
                "exam_id": q.exam_id,
                "content": q.content,
                "knowledge_points": q.knowledge_points,
                "difficulty": q.difficulty,
                "source": q.source,
                "year": q.year,
                "region": q.region,
                "question_type": q.question_type,
                "question_number": q.question_number,
                "answer": q.answer,
            })

        count = self.index_questions(questions_for_index)
        print(f"Indexed {count} vectors to vector store (from {len(questions_for_index)} questions)")
        return count

    def get_index_stats(self) -> Dict:
        """获取索引统计信息"""
        if not self.collection:
            return {"status": "not_available"}

        try:
            count = self.collection.count()
            return {
                "status": "ready",
                "question_count": count,
                "chroma_path": self.chroma_path
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


# 全局实例
vector_search_service = VectorSearchService()

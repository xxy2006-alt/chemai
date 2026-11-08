#!/usr/bin/env python3
"""
ChemAI CLI 工具
用于: 初始化数据库/导入题库/启动服务/测试
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def init_database():
    """初始化数据库"""
    print("Initializing database...")
    from app.models.database import init_db

    # 创建所有表
    init_db()
    print("Database tables created!")

    # 验证表
    from app.models.database import engine
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables: {', '.join(tables)}")


def init_knowledge_graph():
    """初始化知识图谱"""
    print("初始化知识图谱...")
    from app.services.knowledge_graph import kg_service
    kp_count = len(kg_service.knowledge_points)
    print(f"已加载 {kp_count} 个知识点")
    return kp_count


def init_exam_bank():
    """初始化题库"""
    print("初始化题库...")
    from app.services.exam_bank import exam_bank_service
    q_count = len(exam_bank_service.questions)
    p_count = len(exam_bank_service.papers)
    print(f"已加载 {q_count} 题, 覆盖 {p_count} 套试卷")
    return q_count


def test_chemical_balance():
    """测试化学方程式审核引擎"""
    print("\n测试化学方程式审核引擎...")

    from app.services.chemical_balance import check_equation_balance

    test_cases = [
        "2H2 + O2 → 2H2O",      # 配平
        "H2 + O2 → H2O",         # 未配平
        "CH4 + 2O2 → CO2 + 2H2O",  # 配平
        "2Fe + O2 → 2FeO",       # 配平
        "Fe + O2 → Fe2O3",        # 未配平
    ]

    for eq in test_cases:
        result = check_equation_balance(eq)
        status = "[OK]" if result.is_balanced else "[FAIL]"
        print(f"  {status} {eq}")
        if not result.is_balanced:
            print(f"    -> {result.message}")


def test_exam_bank():
    """测试题库服务"""
    print("\n测试题库服务...")

    from app.services.exam_bank import exam_bank_service

    # 测试搜索
    results = exam_bank_service.search_questions(knowledge_point="盐类水解")
    print(f"  知识点'盐类水解'相关题目: {len(results)}道")

    # 测试相似题目
    if results:
        similar = exam_bank_service.find_similar_questions(
            knowledge_points=results[0].knowledge_points,
            difficulty="medium",
            limit=3
        )
        print(f"  相似题目: {len(similar)}道")

    # 测试统计
    stats = exam_bank_service.get_knowledge_point_stats()
    print(f"  知识点统计: {len(stats)}个知识点")


def start_server(host: str = "0.0.0.0", port: int = 8000):
    """启动FastAPI服务"""
    import uvicorn
    print(f"启动ChemAI服务 on {host}:{port}...")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )


def show_stats():
    """显示系统统计"""
    print("\n" + "=" * 50)
    print("ChemAI System Status")
    print("=" * 50)

    # 数据库
    from sqlalchemy import create_engine, inspect
    engine = create_engine("sqlite:///./chemai.db")
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\nDatabase: {engine.url.database}")
    print(f"Tables: {len(tables)} - {', '.join(tables) if tables else 'none'}")

    # 知识图谱
    from app.services.knowledge_graph import kg_service
    print("\nKnowledge Graph:")
    print(f"  Knowledge Points: {len(kg_service.knowledge_points)}")

    # 题库
    from app.services.exam_bank import exam_bank_service
    print("\nExam Bank:")
    print(f"  Total Questions: {len(exam_bank_service.questions)}")
    print(f"  Papers: {len(exam_bank_service.papers)}")

    # 按来源分布
    sources = {}
    for q in exam_bank_service.questions:
        src = q.source
        sources[src] = sources.get(src, 0) + 1
    print("  By Source:")
    for src, count in sorted(sources.items()):
        print(f"    {src}: {count} questions")

    # 知识点统计
    stats = exam_bank_service.get_knowledge_point_stats()
    print(f"\nKnowledge Points Coverage: {len(stats)}")

    print("\n" + "=" * 50)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="ChemAI CLI工具")
    parser.add_argument("command", choices=["init", "test", "stats", "server"],
                       help="命令: init=初始化, test=测试, stats=统计, server=启动服务")
    parser.add_argument("--host", default="0.0.0.0", help="服务主机(默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="服务端口(默认: 8000)")

    args = parser.parse_args()

    if args.command == "init":
        init_database()
        init_knowledge_graph()
        init_exam_bank()
        print("\n初始化完成!")

    elif args.command == "test":
        test_chemical_balance()
        test_exam_bank()
        print("\n测试完成!")

    elif args.command == "stats":
        show_stats()

    elif args.command == "server":
        start_server(args.host, args.port)


if __name__ == "__main__":
    main()

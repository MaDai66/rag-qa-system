from jinja2 import Environment, FileSystemLoader
import os
from config.conf import PROJECT_DIR

def test_template():
    # env = Environment(loader=FileSystemLoader(PROJECT_DIR))
    # print(PROJECT_DIR)
    
    # env = Environment(loader=FileSystemLoader(os.path.dirname(__file__)))
    # print(os.path.dirname(__file__))
    # print(os.path.join(os.path.dirname(__file__), "embedding_search.sql.j2"))
    # 允许从多个目录查找模板
    loader = FileSystemLoader([
        os.path.dirname(__file__),  # 当前脚本目录
        os.path.join(PROJECT_DIR, "langchat", "dao", "sql")  # 实际模板存放路径
    ])
    env = Environment(loader=loader)

    try:
        template_path = os.path.join( "embedding_search.sql.j2")
        # template_path = os.path.join("tests","embedding_search.sql.j2")
        print(f"template_path:{template_path}")
        template = env.get_template(template_path)
        print("✅ Template loaded successfully.")
        print(template.render(collection_id=1, top_n=5, score_threshold=0.5, query_embedding=[0.1, 0.2]))
    except Exception as e:
        print(f"❌ Template error: {e}")


if  __name__ == "__main__":
    test_template()
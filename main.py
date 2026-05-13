# main.py
from backend.agent_core import start_agent

# 主菜单
def main():
    print("=== AI Agent 主入口 ===")
    print("输入 1 启动，输入 0 退出\n")
    
    while True:
        choice = input("请选择 (1=启动, 0=退出)：")
        if choice == "1":
            start_agent()
        elif choice == "0":
            print("再见！")
            break
        else:
            print("输入无效，请重试\n")

if __name__ == "__main__":
    main()

import tkinter as tk
from tkinter import messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from net_utils import get_social_network, process_user
import asyncio

class SocialNetworkApp:
    def __init__(self, root):
        self.root = root
        self.root.geometry("600x600")

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.title("Social Network Visualizer")
        
        self.user_id_label = tk.Label(root, text="Enter User ID:")
        self.user_id_label.pack(pady=10)
        
        self.user_id_entry = tk.Entry(root)
        self.user_id_entry.pack(pady=5)
        
        self.submit_button = tk.Button(root, text="Submit", command=self.display_info)
        self.submit_button.pack(pady=10)
        
        self.info_text = tk.Text(root, height=5, width=50)
        self.info_text.pack(pady=10)
        
        self.canvas_frame = tk.Frame(root)
        self.canvas_frame.pack(pady=10)
    
    def display_info(self):
        user_input = self.user_id_entry.get()
        try:
            user_id = int(user_input)
        except ValueError:
            messagebox.showwarning("Input Error", "Please enter a valid integer User ID.")
            return
        
        # 显示“爬取中”
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, "爬取中...")
        
        # 更新界面以显示“爬取中”
        self.root.update_idletasks()
        
        info_message = asyncio.run(process_user(user_id))
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(tk.END, info_message)
        
        fig = get_social_network(user_id)
        self.update_plot(fig)

    def update_plot(self, fig):
        canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def on_closing(self):
        # 确保关闭窗口时程序完全终止
        self.root.destroy()
        exit()  # 显式退出程序

if __name__ == "__main__":
    root = tk.Tk()
    app = SocialNetworkApp(root)
    root.mainloop()




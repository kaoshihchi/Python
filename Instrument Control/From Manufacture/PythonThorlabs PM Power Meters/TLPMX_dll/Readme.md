📌 1. 範例用途

這個資料夾提供 Python 範例程式，教你怎麼用 TLPMx 驅動 DLL 來控制 Thorlabs 的 PMxxx 光功率計。

適用於 支援 TLPMx 驅動的 Power Meter 型號。

範例程式全部是用 Python 的 ctypes 函式庫來載入 DLL。

📌 2. 必要條件

你的電腦需要安裝 ctypes (Python 標準庫通常已內建)。

需要 TLPMX DLL 檔案，Python 程式會用 LoadLibrary 來載入它。

📌 3. 載入 DLL 的三種方式

程式裡有三種 cdll.LoadLibrary(...) 寫法，代表不同的 DLL 搜尋位置：

當前資料夾（例如 DLL 和程式放在一起）

self.dll = cdll.LoadLibrary(".\\TLPMX_64.dll")


系統環境路徑（DLL 已經安裝在系統 PATH 或 Windows System32 之類目錄）

self.dll = cdll.LoadLibrary("TLPMX_64.dll")


指定絕對路徑（例如驅動安裝在 C:\Program Files\...）

self.dll = cdll.LoadLibrary("C:\\Program Files\\IVI Foundation\\VISA\\Win64\\Bin\\TLPMX_64.dll")


👉 你要根據自己 DLL 安裝位置修改。

📌 4. 檔案內容

TLPMX.py

定義一個 TLPMX 類別

裡面有這些儀器控制用的「方法」和「常數」

是核心的 DLL 封裝 (wrapper)。

PMxxx using ctypes - Python 3.py

範例程式：連接到一般 PMxxx 功率計

設定量測參數

讀取並顯示功率值。

PM5020 using ctypes - Python 3.py

範例程式：連接到 PM5020 雙通道功率計

設定參數後，讀取並顯示功率值。

PM103E_ctypes_connectwithNetSearch.py

範例：透過 網路搜尋 (network mask) 找到 PM103E 並連接。

PM103E_ctypes_connectwithIP.py

範例：直接用 IP 位址 連接 PM103E。

📌 5. 更多範例程式

除了這個 repo 的程式，安裝 Thorlabs 的 Optical Power Monitor 軟體後，也會在這裡附帶 Python 範例：

C:\Program Files (x86)\IVI Foundation\VISA\WinNT\TLPMX\Examples\Python
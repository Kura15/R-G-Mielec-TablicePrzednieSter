import threading
import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk, scrolledtext

# ============================================================
#  MAPOWANIE ZNAKÓW - KODOWANIE CP 667 (Dla tablic ETKL)
# ============================================================
# Tablica używa sprzętowego CP 667 (zmodyfikowane CP 437).
# Zaktualizowane na podstawie przesłanej tabeli znaków.
ETKL_CHAR_MAP = {
    'Ą': 0x8F, 'Ć': 0x95, 'Ę': 0x90, 'Ł': 0x9C, 'Ń': 0xA5, 'Ó': 0xA3, 'Ś': 0x98, 'Ź': 0xA0, 'Ż': 0xA1,
    'ą': 0x86, 'ć': 0x8D, 'ę': 0x91, 'ł': 0x92, 'ń': 0xA4, 'ó': 0xA2, 'ś': 0x9E, 'ź': 0xA6, 'ż': 0xA7
}

# ============================================================
#  SUMA KONTROLNA ASCII‑HEX
# ============================================================

def checksum_ascii_hex(payload: bytes) -> bytes:
    s = sum(payload) & 0xFF
    hex_str = f"{s:02X}"
    return bytes([ord(hex_str[0]), ord(hex_str[1])])


# ============================================================
#  BUDOWANIE RAMKI
# ============================================================

def build_frame(payload: bytes) -> bytes:
    chk = checksum_ascii_hex(payload)
    return b"\xFF\x02" + payload + chk + b"\x03"


def build_37_45_frame(rest: bytes) -> bytes:
    """
    Buduje payload:
    37 45 <LEN_HI><LEN_LO> <rest...>
    gdzie LEN to długość <rest> w bajtach, zakodowana jako ASCII‑HEX.
    """
    length = len(rest)
    length_hex = f"{length:02X}"
    len_bytes = bytes([ord(length_hex[0]), ord(length_hex[1])])
    payload = b"\x37\x45" + len_bytes + rest
    return build_frame(payload)


# ============================================================
#  KONWERSJA TEKSTU NA BAJTY (CP 667 / CP 437)
# ============================================================

def ascii_to_hex_bytes(text: str) -> bytes:
    text = text or ""
    if text == "":
        return b"\x00"
    
    output_bytes = bytearray()
    
    for char in text:
        if char in ETKL_CHAR_MAP:
            # Polskie litery z mapowania CP 667
            output_bytes.append(ETKL_CHAR_MAP[char])
        else:
            try:
                # Reszta znaków domyślnie jako sprzętowe CP 437 wyświetlacza
                output_bytes.extend(char.encode("cp437"))
            except UnicodeEncodeError:
                # Jeśli znaku nie ma ani w CP 667, ani w CP 437 (np. emoji), wstawiamy spację
                output_bytes.append(0x20) 
                
    return bytes(output_bytes)


# ============================================================
#  KONTROLER PORTU
# ============================================================

class SerialController:
    def __init__(self, log_callback):
        self.ser = None
        self.log_callback = log_callback
        self.running = False

    def open(self, port, baudrate):
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                parity=serial.PARITY_NONE,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            self.running = True
            threading.Thread(target=self.read_loop, daemon=True).start()
            self.log_callback(f"[INFO] Otwarty port {port}\n")
        except Exception as e:
            self.log_callback(f"[ERROR] {e}\n")

    def close(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.log_callback("[INFO] Zamknięto port\n")

    def read_loop(self):
        while self.running and self.ser and self.ser.is_open:
            try:
                data = self.ser.read(1024)
                if data:
                    self.log_callback(f"[RX] {data.hex(' ').upper()}\n")
            except:
                break

    def send(self, frame: bytes):
        if not self.ser or not self.ser.is_open:
            self.log_callback("[ERROR] Port nie jest otwarty\n")
            return
        self.ser.write(frame)
        self.log_callback(f"[TX] {frame.hex(' ').upper()}\n")


# ============================================================
#  GUI
# ============================================================

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Sterowanie tablicą")

        self.serial = SerialController(self.log)

        # ---------------- COM ----------------
        frame_com = ttk.LabelFrame(root, text="Port COM")
        frame_com.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        ttk.Label(frame_com, text="Port:").grid(row=0, column=0)
        self.port_var = tk.StringVar()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_box = ttk.Combobox(frame_com, textvariable=self.port_var, values=ports, width=10)
        self.port_box.grid(row=0, column=1)

        ttk.Label(frame_com, text="Baud:").grid(row=0, column=2)
        self.baud_var = tk.IntVar(value=9600)
        ttk.Entry(frame_com, textvariable=self.baud_var, width=8).grid(row=0, column=3)

        ttk.Button(frame_com, text="Otwórz", command=self.open_port).grid(row=0, column=4, padx=5)
        ttk.Button(frame_com, text="Zamknij", command=self.close_port).grid(row=0, column=5, padx=5)

        # ---------------- Dane ----------------
        frame_data = ttk.LabelFrame(root, text="Dane")
        frame_data.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        ttk.Label(frame_data, text="Nr linii:").grid(row=0, column=0, sticky="w")
        self.nr_linii_var = tk.StringVar()
        ttk.Entry(frame_data, textvariable=self.nr_linii_var, width=20).grid(row=0, column=1)

        ttk.Label(frame_data, text="Kierunek K1:").grid(row=1, column=0, sticky="w")
        self.k1_var = tk.StringVar()
        ttk.Entry(frame_data, textvariable=self.k1_var, width=20).grid(row=1, column=1)

        ttk.Label(frame_data, text="Kierunek K2:").grid(row=2, column=0, sticky="w")
        self.k2_var = tk.StringVar()
        ttk.Entry(frame_data, textvariable=self.k2_var, width=20).grid(row=2, column=1)

        self.double_mode = tk.BooleanVar()
        ttk.Checkbutton(frame_data, text="Tryb dwuliniowy", variable=self.double_mode).grid(row=3, column=0, columnspan=2)

        # ---------------- Przyciski ----------------
        frame_btn = ttk.Frame(root)
        frame_btn.grid(row=2, column=0, pady=5)

        ttk.Button(frame_btn, text="Wyślij", command=self.send_all).grid(row=0, column=0, padx=5)
        ttk.Button(frame_btn, text="Negatyw", command=self.send_negatyw).grid(row=0, column=1, padx=5)
        ttk.Button(frame_btn, text="Wyczyść", command=self.send_clear).grid(row=0, column=2, padx=5)

        # ---------------- Konsola ----------------
        frame_console = ttk.LabelFrame(root, text="Konsola")
        frame_console.grid(row=3, column=0, sticky="nsew", padx=5, pady=5)

        self.console = scrolledtext.ScrolledText(frame_console, width=90, height=25)
        self.console.grid(row=0, column=0)

        root.grid_rowconfigure(3, weight=1)
        root.grid_columnconfigure(0, weight=1)

    # ============================================================
    #  LOG
    # ============================================================

    def log(self, text):
        self.console.insert(tk.END, text)
        self.console.see(tk.END)

    # ============================================================
    #  PORT
    # ============================================================

    def open_port(self):
        self.serial.open(self.port_var.get(), self.baud_var.get())

    def close_port(self):
        self.serial.close()

    # ============================================================
    #  KOMENDY STAŁE (bez sumy!)
    # ============================================================

    def set_clear(self):
        # FF 02 37 46 30 32 30 41 35 30 03
        frame = bytes.fromhex("FF 02 37 46 30 32 30 41 35 30 03")
        self.serial.send(frame)

    def send_clear(self):
        self.set_clear()
        self.send_zatwierdz()

    def send_negatyw(self):
        # FF 02 37 46 30 32 33 39 34 42 03
        frame = bytes.fromhex("FF 02 37 46 30 32 33 39 34 42 03")
        self.serial.send(frame)

    def send_zatwierdz(self):
        # FF 02 37 46 30 32 30 38 34 37 03
        frame = bytes.fromhex("FF 02 37 46 30 32 30 38 34 37 03")
        self.serial.send(frame)

    # ============================================================
    #  WYSYŁANIE KIERUNKÓW
    # ============================================================

    def send_all(self):
        # 1) Wyczyść tablicę (bez zatwierdzania na końcu – zatwierdzimy po wszystkim)
        self.set_clear()

        # 2) Nr linii
        nr_bytes = ascii_to_hex_bytes(self.nr_linii_var.get())
        # rest: "Linia" + 00 + <nr> + 00
        rest_nr = bytes.fromhex("4C 69 6E 69 61 00") + nr_bytes + b"\x00"
        frame_nr = build_37_45_frame(rest_nr)
        self.serial.send(frame_nr)

        # 3) Tekst K1 i K2
        k1 = ascii_to_hex_bytes(self.k1_var.get())
        k2 = ascii_to_hex_bytes(self.k2_var.get())

        if not self.double_mode.get():
            # ---------------- TRYB JEDNOLINIOWY ----------------
            # Kier A: "Kier" 00 <K1> 00
            rest_a = bytes.fromhex("4B 69 65 72 00") + k1 + b"\x00"
            frame_a = build_37_45_frame(rest_a)

            # Kier B: "KierB" 00 <K1> 00
            rest_b = bytes.fromhex("4B 69 65 72 42 00") + k1 + b"\x00"
            frame_b = build_37_45_frame(rest_b)

            self.serial.send(frame_a)
            self.serial.send(frame_b)

        else:
            # ---------------- TRYB DWULINIOWY ----------------
            # Kier A: "KierL1" 00 <K1> 00 "KierL2" 00 <K2> 00
            rest_a = (
                bytes.fromhex("4B 69 65 72 4C 31 00")
                + k1 + b"\x00"
                + bytes.fromhex("4B 69 65 72 4C 32 00")
                + k2 + b"\x00"
            )
            frame_a = build_37_45_frame(rest_a)

            # Kier B: "KierB1" 00 <K1> 00 "KierB2" 00 <K2> 00
            rest_b = (
                bytes.fromhex("4B 69 65 72 42 31 00")
                + k1 + b"\x00"
                + bytes.fromhex("4B 69 65 72 42 32 00")
                + k2 + b"\x00"
            )
            frame_b = build_37_45_frame(rest_b)

            self.serial.send(frame_a)
            self.serial.send(frame_b)

        # 4) Zatwierdzanie
        self.send_zatwierdz()


# ============================================================
#  START
# ============================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
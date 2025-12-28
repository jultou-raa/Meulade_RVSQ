import customtkinter as ctk
import threading
import webbrowser
from languages import translations, languages
import browser
import sys
import os
import shutil
from logger import default_message_queue, log_message
import security
from PIL import Image

class SharedBoolean:
    def __init__(self, initial_value):
        self.value = initial_value
        self.lock = threading.Lock()

    def set(self, new_value):
        with self.lock:
            self.value = new_value

    def get(self):
        with self.lock:
            return self.value

class AppGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("RVSQ Appointment Finder")
        self.geometry("500x850")
        
        # Set theme
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        
        # Constants
        self.BLUE = "#3f83f8"
        self.GREEN = "#22c55e"
        self.RED = "#ef4444"
        
        # Initialize translations and languages
        self.translations = translations
        self.languages = languages
        self.current_language = 'Français'
        
        # State
        self.search_running = SharedBoolean(False)
        self.autobook = True
        
        # Load logo
        self.logo = None
        try:
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            
            logo_path = os.path.join(base_path, 'images', 'logo_small.png')
            if os.path.exists(logo_path):
                 self.logo = ctk.CTkImage(light_image=Image.open(logo_path),
                                          dark_image=Image.open(logo_path),
                                          size=(100, 100))
        except Exception as e:
            print(f"Warning: Could not load logo image: {str(e)}")

        self.setup_ui()
        self.load_saved_config()
        
        # Start status update loop
        self.update_status()

    def setup_ui(self):
        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main scrollable frame
        self.main_frame = ctk.CTkScrollableFrame(self)
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Header Frame (Logo + Title)
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, pady=(10, 20), sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)

        if self.logo:
            self.logo_label = ctk.CTkLabel(self.header_frame, image=self.logo, text="")
            self.logo_label.grid(row=0, column=0, pady=(0, 10))

        self.title_label = ctk.CTkLabel(self.header_frame,
                                      text=self.get_text('app_title'),
                                      font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.grid(row=1, column=0)
        
        # Language Selector (Top Right)
        self.language_var = ctk.StringVar(value=self.current_language)
        self.language_menu = ctk.CTkOptionMenu(self.header_frame,
                                             values=self.languages,
                                             command=self.change_language,
                                             variable=self.language_var,
                                             width=100)
        self.language_menu.place(relx=1.0, rely=0.0, anchor="ne")

        # Input Fields Frame
        self.input_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.input_frame.grid(row=1, column=0, sticky="ew", padx=20)
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.fields = {}
        field_configs = [
            ('first_name', 'first_name'),
            ('last_name', 'last_name'),
            ('nam', 'nam'),
            ('card_seq_number', 'card_seq_number'),
            ('postal_code', 'postal_code'),
            ('cellphone', 'cellphone'),
            ('email', 'email')
        ]

        current_row = 0
        for key, lang_key in field_configs:
            label = ctk.CTkLabel(self.input_frame, text=self.get_text(lang_key), anchor="w")
            label.grid(row=current_row, column=0, sticky="w", pady=(5, 0))

            entry = ctk.CTkEntry(self.input_frame, placeholder_text=self.get_text(f'placeholder_{lang_key}'))
            entry.grid(row=current_row + 1, column=0, sticky="ew", pady=(0, 5))

            self.fields[key] = {'entry': entry, 'label': label, 'key': lang_key}
            current_row += 2

        # Birth Date Fields
        self.birth_label = ctk.CTkLabel(self.input_frame, text="Birth Date", anchor="w") # Label will be updated
        self.birth_label.grid(row=current_row, column=0, sticky="w", pady=(5, 0))
        
        self.birth_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        self.birth_frame.grid(row=current_row + 1, column=0, sticky="ew", pady=(0, 5))
        self.birth_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.fields['birth_day'] = {'entry': ctk.CTkEntry(self.birth_frame, placeholder_text="DD"), 'key': 'birth_day'}
        self.fields['birth_day']['entry'].grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.fields['birth_month'] = {'entry': ctk.CTkEntry(self.birth_frame, placeholder_text="MM"), 'key': 'birth_month'} # Usually a select in HTML, but keeping text for now or maybe switch to OptionMenu
        # Actually RVSQ uses a dropdown for month usually (01, 02...). Let's stick to text for simplicity but maybe OptionMenu is better?
        # The original code had text input for day and year, and select for month.
        # Let's use OptionMenu for month.
        months = [str(i).zfill(2) for i in range(1, 13)]
        self.fields['birth_month']['entry'] = ctk.CTkOptionMenu(self.birth_frame, values=months)
        self.fields['birth_month']['entry'].grid(row=0, column=1, padx=5, sticky="ew")
        
        self.fields['birth_year'] = {'entry': ctk.CTkEntry(self.birth_frame, placeholder_text="YYYY"), 'key': 'birth_year'}
        self.fields['birth_year']['entry'].grid(row=0, column=2, padx=(5, 0), sticky="ew")
        
        current_row += 2

        # Consulting Reason
        self.reason_label = ctk.CTkLabel(self.input_frame, text="Raison de consultation", anchor="w")
        self.reason_label.grid(row=current_row, column=0, sticky="w", pady=(5, 0))
        
        # Options from RVSQ
        # We need the values for the select option.
        # Based on typical RVSQ values. The user mentioned one: 'ac2a5fa4-8514-11ef-a759-005056b11d6c' (Consultation Urgente)
        # I should probably provide a map.
        self.reason_options = {
            "Consultation Urgente": "ac2a5fa4-8514-11ef-a759-005056b11d6c",
            "Suivi régulier": "suivi_regulier_value_placeholder", # I don't have this value yet, need to find it or let user input it?
            # Actually, without the values, it's hard. But the user said: "mon GMF n'ajoute que des rdv en suivis réguliers".
            # Maybe I should just provide a way to select "Consultation Urgente" or "Suivi de routine" if I can find the ID.
            # If I can't find the ID, I might need to look it up dynamically or ask the user to provide it?
            # Or maybe just "Urgence Mineure" vs "Suivi".
            # Let's assume for now I only have the one from the code.
            # Wait, if I don't have the value, I can't select it.
            # However, `browser.py` hardcodes it.
            # Maybe I should list common reasons if I can find them.
            # If not, I will just put the one I know and maybe "Other" (and try to handle it dynamically? No that's hard).
            # The issue says "Il faudrait laisser au user le choix du consultingReason".
            # The user might know the value or maybe I can scrape it?
            # But I can't scrape it easily without login or being on the page.
            # Let's look at `browser.py` again. It selects by value.
            # `page.select_option('#consultingReason', 'ac2a5fa4-8514-11ef-a759-005056b11d6c')`
            
            # I will add a few common ones if I can find them on google.
            # Otherwise, I'll add "Consultation Urgente" and maybe a text entry for "Other (Value)"?
            # Or better, just "Consultation Urgente" and "Suivi médical" if I can guess the ID.
            # Let's try to search online for "RVSQ consultingReason values".
        }

        # For now, I'll stick to what I have and maybe add a generic text field if "Custom" is selected?
        # Or better, just put the one we have and maybe a text field for "Custom ID" for advanced users?
        # The user on github said "mon GMF n'ajoute que des rdv en suivis réguliers".
        # So they probably know what they want.
        
        self.reason_var = ctk.StringVar(value="Consultation Urgente")
        self.reason_menu = ctk.CTkOptionMenu(self.input_frame,
                                             values=["Consultation Urgente", "Custom ID"],
                                             command=self.on_reason_change,
                                             variable=self.reason_var)
        self.reason_menu.grid(row=current_row + 1, column=0, sticky="ew", pady=(0, 5))
        
        self.custom_reason_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Enter Custom Reason ID")
        self.custom_reason_entry.grid(row=current_row + 2, column=0, sticky="ew", pady=(0, 5))
        self.custom_reason_entry.grid_remove() # Hide initially

        current_row += 3

        # Website Selection
        self.website_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        self.website_frame.grid(row=current_row, column=0, sticky="ew", pady=(10, 5))

        self.rvsq_var = ctk.BooleanVar(value=True)
        self.rvsq_checkbox = ctk.CTkCheckBox(self.website_frame, text="RVSQ", variable=self.rvsq_var)
        self.rvsq_checkbox.grid(row=0, column=0, padx=10)

        self.bonjour_var = ctk.BooleanVar(value=False)
        self.bonjour_checkbox = ctk.CTkCheckBox(self.website_frame, text="Bonjour Santé", variable=self.bonjour_var)
        self.bonjour_checkbox.grid(row=0, column=1, padx=10)

        current_row += 1

        # Buttons
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.grid(row=2, column=0, pady=20)

        self.start_button = ctk.CTkButton(self.button_frame,
                                        text=self.get_text('start'),
                                        command=self.start_search,
                                        fg_color=self.GREEN,
                                        hover_color="#15803d")
        self.start_button.grid(row=0, column=0, padx=10)

        self.stop_button = ctk.CTkButton(self.button_frame,
                                       text=self.get_text('stop'),
                                       command=self.stop_search,
                                       fg_color=self.RED,
                                       hover_color="#b91c1c",
                                       state="disabled")
        self.stop_button.grid(row=0, column=1, padx=10)

        # Log Area
        self.log_textbox = ctk.CTkTextbox(self.main_frame, height=150)
        self.log_textbox.grid(row=3, column=0, sticky="ew", padx=20, pady=10)
        self.log_textbox.configure(state="disabled")

        # Footer
        self.footer_label = ctk.CTkLabel(self.main_frame,
                                       text="www.meulade.com - " + self.get_text('footer').split(' - ')[-1],
                                       text_color=self.BLUE,
                                       cursor="hand2")
        self.footer_label.grid(row=4, column=0, pady=20)
        self.footer_label.bind("<Button-1>", lambda e: webbrowser.open("https://www.meulade.com"))

    def on_reason_change(self, choice):
        if choice == "Custom ID":
            self.custom_reason_entry.grid()
        else:
            self.custom_reason_entry.grid_remove()

    def get_text(self, key):
        return self.translations.get(self.current_language, self.translations['English']).get(key, key)

    def change_language(self, new_lang):
        self.current_language = new_lang
        self.update_ui_text()

    def update_ui_text(self):
        self.title_label.configure(text=self.get_text('app_title'))
        
        for key, field in self.fields.items():
            if 'label' in field:
                field['label'].configure(text=self.get_text(field['key']))
            if isinstance(field['entry'], ctk.CTkEntry):
                field['entry'].configure(placeholder_text=self.get_text(f"placeholder_{field['key']}"))
        
        self.start_button.configure(text=self.get_text('start'))
        self.stop_button.configure(text=self.get_text('stop'))
        self.footer_label.configure(text="www.meulade.com - " + self.get_text('footer').split(' - ')[-1])
        # Update birth date labels if I added them to translations
        
    def load_saved_config(self):
        config = security.load_encrypted_config()
        if not config:
            return
            
        personal_info = config.get('personal_info', {})
        for key, field in self.fields.items():
            if key in personal_info:
                if isinstance(field['entry'], ctk.CTkEntry):
                    field['entry'].delete(0, 'end')
                    field['entry'].insert(0, personal_info[key])
                elif isinstance(field['entry'], ctk.CTkOptionMenu):
                     field['entry'].set(personal_info[key])
        
        # Load reason
        if 'reason_id' in personal_info:
            reason_id = personal_info['reason_id']
            if reason_id == "ac2a5fa4-8514-11ef-a759-005056b11d6c":
                self.reason_var.set("Consultation Urgente")
            else:
                self.reason_var.set("Custom ID")
                self.custom_reason_entry.grid()
                self.custom_reason_entry.delete(0, 'end')
                self.custom_reason_entry.insert(0, reason_id)

        # Load selected websites (Default RVSQ=True, Bonjour=False if not found)
        self.rvsq_var.set(personal_info.get('rvsq_enabled', True))
        self.bonjour_var.set(personal_info.get('bonjour_enabled', False))

    def save_config(self):
        personal_info = {}
        for key, field in self.fields.items():
             if isinstance(field['entry'], ctk.CTkEntry):
                personal_info[key] = field['entry'].get()
             elif isinstance(field['entry'], ctk.CTkOptionMenu):
                personal_info[key] = field['entry'].get()
        
        # Save reason
        if self.reason_var.get() == "Consultation Urgente":
             personal_info['reason_id'] = "ac2a5fa4-8514-11ef-a759-005056b11d6c"
        else:
             personal_info['reason_id'] = self.custom_reason_entry.get()

        # Save website selection
        personal_info['rvsq_enabled'] = self.rvsq_var.get()
        personal_info['bonjour_enabled'] = self.bonjour_var.get()

        config = {"personal_info": personal_info}
        security.save_encrypted_config(config)
        return config

    def start_search(self):
        # Basic Validation
        for key, field in self.fields.items():
            val = field['entry'].get()
            if not val:
                log_message(f"Error: {key} is required")
                return

        config = self.save_config()
        self.search_running.set(True)

        self.start_button.configure(state="disabled", fg_color="gray")
        self.stop_button.configure(state="normal", fg_color=self.RED)

        # Start threads based on selection
        if self.bonjour_var.get():
            self.search_thread_1 = threading.Thread(target=self.run_search_wrapper, args=('bonjoursante', config, self.search_running, self.autobook))
            self.search_thread_1.daemon = True
            self.search_thread_1.start()

        if self.rvsq_var.get():
            self.search_thread_2 = threading.Thread(target=self.run_search_wrapper, args=('rvsq', config, self.search_running, False))
            self.search_thread_2.daemon = True
            self.search_thread_2.start()

        if not self.rvsq_var.get() and not self.bonjour_var.get():
            log_message("Please select at least one website")
            self.stop_search()

    def stop_search(self):
        self.search_running.set(False)
        self.start_button.configure(state="normal", fg_color=self.GREEN)
        self.stop_button.configure(state="disabled", fg_color="gray")
        log_message("Stopping search...")

    def run_search_wrapper(self, website, config, search_running, autobook):
        try:
            if website == 'rvsq':
                browser.run_automation_rvsq(config, search_running)
            elif website == 'bonjoursante':
                browser.run_automation_bonjoursante(config, search_running, autobook)
        except Exception as e:
            log_message(f"Error in {website}: {str(e)}")
        finally:
            # Clean up browser data after browser closes
            try:
                data_path = os.path.join(os.getcwd(), 'browser_data', website)
                if os.path.exists(data_path):
                    shutil.rmtree(data_path)
                    log_message(f"Browser data cleared for {website}.")
            except Exception as e:
                log_message(f"Error clearing data for {website}: {e}")

            if not search_running.get():
                # If we stopped, update UI in main thread if needed
                pass

    def update_status(self):
        # Update log
        self.log_textbox.configure(state="normal")
        current_text = self.log_textbox.get("1.0", "end")

        # Check if there are new messages
        # efficient way?
        # Just clear and rewrite for now or append new ones
        self.log_textbox.delete("1.0", "end")
        for msg in default_message_queue[-10:]:
            self.log_textbox.insert("end", msg + "\n")

        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

        # Check running state to update buttons if stopped from thread
        if not self.search_running.get() and self.stop_button._state == "normal":
             self.stop_search()

        self.after(500, self.update_status)

    def run(self):
        self.mainloop()

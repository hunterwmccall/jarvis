# testmouse.py — isolates pyautogui from the vision pipeline
import ctypes, time
ctypes.windll.user32.SetProcessDPIAware()      # must run BEFORE importing pyautogui
import pyautogui

print("pyautogui thinks the screen is:", pyautogui.size())
print("moving in 3 seconds — click into Chrome now")
time.sleep(3)
pyautogui.moveTo(500, 375, duration=0.5)
print("cursor is now at:", pyautogui.position())
pyautogui.click()
print("clicked")
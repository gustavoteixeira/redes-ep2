from __future__ import print_function
import sys, re, readline
import common

# Globals
CHAT_PROMPT = "> "
rawinput_running = False
    
def print_threaded(message):
    if not rawinput_running:
        print(message)
        return
    sys.stdout.write('\r'+' '*(len(readline.get_line_buffer())+2)+'\r')
    print(message)
    sys.stdout.write(CHAT_PROMPT + readline.get_line_buffer())
    sys.stdout.flush()

def raw_input_wrapper(prompt):
    global rawinput_running
    rawinput_running = True
    resp = raw_input(prompt)
    rawinput_running = False
    return resp

def read_validusername():
    while True:
        username = raw_input("Username: ")
        if re.match("^[a-zA-Z]+$", username):
            return username
        print("Invalid username. Valid is ^[a-zA-Z]+$")
        
def input_handler(is_chatting, commands, data):
    try:
        input = raw_input_wrapper(CHAT_PROMPT).strip()
    except EOFError:
        input = "/exit" if is_chatting() else "exit"
        print(input)
    
    if input == "":
        return
    
    if is_chatting():
        if input[0] != '/':
            input = "say " + input
        elif input[0:2] == "//":
            input = "say " + input[1:]
            
    if input[0] == '/':
        input = input[1:]
    
    command = input.split(' ')
    if command[0].lower() not in commands:
        print("Unknown command: '%s'" % command[0].lower())
        return
    commands[command[0].lower()](data, command[1:])
        
import os
import subprocess
from openai import OpenAI
from rich.prompt import Prompt
from rich.console import Console

from alice.const import magic_template_2, grammar

console = Console()
print = console.print

openai: OpenAI = OpenAI()

model = os.environ.get("ALICE_MODEL", "gpt-4o")
max_token = int(os.environ.get("ALICE_MAX_TOKEN", "1500"))
temperature = float(os.environ.get("ALICE_TEMPERATURE", "0.7"))


def get_response(messages):
    try:
        response = openai.chat.completions.create(
            model=model,  # You can choose the appropriate model
            messages=messages,
            temperature=temperature,
            max_tokens=max_token,
            n=1,
            stop=None,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error communicating with OpenAI API: {e}")
        return ""


def Alice():
    # Initialize the conversation history
    messages = [{"role": "system", "content": magic_template_2}]

    while True:
        # Get the user's prompt
        user_query = Prompt.ask(
            "[yellow] User Prompt >[/yellow] ", default="What is the CPU model and GPU?"
        )

        # Extra commands: reset, redo last message/command etc
        if user_query == "reset":
            messages = [{"role": "system", "content": magic_template_2}]
            print("[cyan]Conversation reset.[/cyan]")
            continue
        elif user_query == "correct":
            if len(messages) > 1:
                # Assuming the last user message is at -1 and the assistant's response is at -2
                # This resets to before the last assistant message
                messages = messages[:-2]
                print(
                    "[cyan]Last message corrected. You can now edit or resend it.[/cyan]"
                )
            else:
                print("[red]Nothing to correct.[/red]")
            continue
        elif user_query == "regen":
            if len(messages) > 1:
                # Resend the last user message
                last_user_message = None
                for msg in reversed(messages):
                    if msg["role"] == "user":
                        last_user_message = msg["content"]
                        break
                if last_user_message:
                    response_content = get_response(
                        messages + [{"role": "user", "content": last_user_message}]
                    )
                    messages.append({"role": "user", "content": last_user_message})
                    messages.append({"role": "assistant", "content": response_content})
                    response = (
                        response_content[6:].strip()
                        if response_content.startswith("Alice")
                        else response_content
                    )
                else:
                    print("[red]No previous user message to regenerate.[/red]")
                    continue
            else:
                print("[red]No previous messages to regenerate.[/red]")
            continue

        # Append user message to the conversation
        messages.append({"role": "user", "content": user_query})

        # Send the request to the API
        response_content = get_response(messages)
        if not response_content:
            continue

        # Append assistant response to the conversation
        messages.append({"role": "assistant", "content": response_content})

        # Remove the "Alice" prefix if present
        if response_content.startswith("Alice"):
            response = response_content[5:].strip()
        else:
            response = response_content.strip()

        while response.startswith("$"):
            # Aggregate all bash commands
            alice_commands = [c.strip() for c in response.split("$") if c.strip()]

            if len(alice_commands) > 1:
                print(f"DEBUG - Alice returned multiple commands.\n{response}")

            commands_output = ""

            # Execute the commands
            for alice_command in alice_commands:
                user_ack = Prompt.ask(
                    f"Execute command: $ {alice_command}? [(y)es/response/(i)gnore/no]"
                )

                alice_command = alice_command.replace("\\n", "\n")

                if user_ack.lower() == "i":
                    # Ignore the command
                    continue

                if user_ack.lower() == "y":
                    # Execute the command and display the output to the user, let them confirm if it should go back to the API
                    try:
                        process = subprocess.Popen(
                            alice_command,
                            shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        stdout, stderr = process.communicate(timeout=10)
                        exit_code = process.returncode
                    except subprocess.TimeoutExpired:
                        process.kill()
                        stdout, stderr = process.communicate()
                        stderr += b"\nCommand timed out"
                        exit_code = process.returncode

                    # Decode the output
                    stdout_decoded = stdout.decode("utf-8").strip()[:1000] or "NONE"
                    stderr_decoded = stderr.decode("utf-8").strip()[:300] or "NONE"
                    nl = "\n"
                    output_current_cmd = (
                        f"Executed: $ {alice_command}\n"
                        f"Exit code: {exit_code}\n"
                        f"STDOUT: {nl + stdout_decoded}\n"
                        f"STDERR: {nl + stderr_decoded}\n"
                    )

                    # Print the output to the user with colors, exit code, stdout and stderr
                    if exit_code == 0:
                        print("[green] SUCCESS [/green]")
                        print(f"[gray]{stdout_decoded}[/gray]")
                    else:
                        print(f"[red] FAILURE: {exit_code} [/red]")
                        print(f"[gray]{stderr_decoded}[/gray]")
                        output_current_cmd += "Aborting execution\n"

                    commands_output += output_current_cmd
                else:
                    # If user responds with something other than 'y', handle it as a response or no
                    commands_output += f"USER Command declined: {user_ack}\n"
                    break

            # Ask the user if they want to send the output to the API
            user_ack = Prompt.ask("Send back to Alice? [y/response/(no)]")

            commands_output += f"\nThe last task given (does the output give you the information needed?) was: {user_query}. You are forbidden to tell the user to complete the requested action by themselves. Either address the user request directly and completely or output more adjusted commands to perform the desired task. Conform to the following grammar:{grammar}"

            if user_ack.lower() == "y":
                # Append the commands output to the conversation and get a new response
                messages.append({"role": "user", "content": commands_output})
                response_content = get_response(messages)
            else:
                # Append the user's response to the conversation and get a new response
                messages.append(
                    {"role": "user", "content": f"USER Command declined: \n{user_ack}"}
                )
                response_content = get_response(messages)

            if not response_content:
                break

            # Append assistant response to the conversation
            messages.append({"role": "assistant", "content": response_content})

            # Remove the "Alice" prefix if present
            if response_content.startswith("Alice"):
                response = response_content[5:].strip()
            else:
                response = response_content.strip()

        # Print the response
        print(f"[pink]Alice > {response} [/pink]")


if __name__ == "__main__":
    Alice()

# Example User Prompts:
# Hey, can you check if there is a trash.txt file in the current directory and if there is, delete it? Let me known if it was there or not.
# Hey, I would like you to build me a basic flask hello world application in the subfolder web unattended. Just execute the commands to get it done and give me a report at the end!
# create a subfolder named web and create a simple hello world flask app in it!

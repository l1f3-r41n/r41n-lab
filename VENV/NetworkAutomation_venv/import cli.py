import cli
import time
import sys
# cli.execute("show ver") - single command
# cli.cli("show ver; show clock") - can do several commands
# cli.configure(["interface GigabitEthernet0/1", "no shutdown", "end"])
tftp_server="10.200.0.1"
def print_line (text, step=None, width=40):
 stext="({})".format(step) if step else "***"
 if step:
 print "\n"
 print "***{}*** {} {}".format(stext, text, "*"*(width-len(text)))
print_line("Checking hardware", 1)
cli.executep("show platform | i Model|C9200|--\ ")
print_line("Checking IOS version", 2)
cli.executep("show version | i IOS XE")
print_line("Generating RSA key", 3)
cli.configurep("crypto key generate rsa modulus 2048 label sshv2logincert")
print_line("Obtaining serial number", 4)
license = cli.cli("show license udi")
sn = license.split(":")[3].rstrip()
print_line("Serial number is {}".format(sn))
print_line("Disabling copy prompts", 5)
cli.configure("file prompt quiet")
print_line("Copying configuration file from TFTP server", 6)
cli_command = "copy tftp://{}/config/{}.txt startup-config vrf Mgmt-vrf".format
(tftp_server, sn.lower())
cli.executep(cli_command)
time.sleep (5)
print_line("Verifying received startup config...", 7)
host_line=cli.cli("show startup-config | i hostname").split()
# actual output will be "Using xxxx out of 2097152 byteshostname sw9200-1A"
if host_line:
 host_name=host_line[-1] # last entry
 print_line("Configuration for {} downloaded successfully!".format(host_name))
 print_line("Rebooting with the new config!", 8)
 cli.cli("reload")
else:
 print("*** *** *** Configuration failed *** *** ***")
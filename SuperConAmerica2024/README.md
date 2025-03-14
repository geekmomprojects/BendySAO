Files for Bendy SAO from SuperCon Amercia 2024

Code diretory contains micropython both code for the badge and for a XIAO 2040 if you choose to run the 
SAO without the badge. 

Due to design issues that cause a conflict with the signal pin which is connected directly to a pin on the XIAO as well as a pin on the badge, the SAO will not work if it is powered from the badge with the XIAO attached, i.e. you can't run code from the XIAO while using the badge for power. If you want to run the SAO from the XIAO, run power through the USB C port on the XIAO.
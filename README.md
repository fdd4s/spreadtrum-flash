# Spreadtrum Flash: opensource NOR memory reader/writer for Spreadtrum SoC of Rockstar Portable MP4 player 

## About

The `uniflash.py` file is the main script to use. The `unicmd.py` file is the library created for easier command interface encapsulation. The `stoned.py` file is the library (as well as a standalone tool) to handle stone image unpacking.  

For further dumped firmware unpacking, I recommend [bzpwork](https://github.com/ilyazx/bzpwork) by ilyazx.  

**Warning: this software is experimental, use at your own risk! You can brick and let unusable your portable mp4 player**  

## Dependencies

Python 3.8+ and PyUSB.  

## Usage as a flasher/dumper

Run `python uniflash.py -h` to see all parameters. But there are several typical scenarios that UniFlash officially supports.  

**Note**: you need to hold a bootkey pressed when connecting the device for it to be detected correctly. This key can vary across devices. Typically it's UP (M) button in Portable MP4 Players, but it can be anything else.  
  
Portable MP4 players require the following procedure to connect in order to initiate successful data transfer:  
  
1. Power off.  
2. Hold the bootkey and then power on.
  
UniFlash ships with several typical targets that you can specify with `-t` (`--target`) parameter and not have to configure anything else:  
  
- `sc6530_generic` - for SC6530 and SC6531B/C/DA with no signed FDLs; Portable MP4 Players use a GSMless version of that SoC  
  
If you want to, the targets are fully overridable with individual parameters, see program help for all details.  

## More related information

https://forums.rockbox.org/index.php/topic,54269.0.html  
  
https://www.youtube.com/@portablemp4 

https://chronovir.us/2021/12/18/Opus-Spreadtrum/ 

## Credits

Original UniFlash created by Luxferre 2022 https://gitlab.com/suborg/uniflash  
All files except the FDL blob are public domain.  
Modified by fdd 2023.  
Send feedback and questions to fdd4776s@gmail.com

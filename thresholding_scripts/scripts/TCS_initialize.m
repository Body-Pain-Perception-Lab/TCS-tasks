%Function used to initialize the connection between the computer and the
%TCS stimulator
%Author: Arthur S. Courtin
%License: MIT

function TCS=TCS_initialize(COMport,baseline_temp)
    % baseline_temp in C
    % COMport is the number of the serial port to which the TCS is
    % connected
    
    disp('Initializing the TCS device. This may take a few seconds.')
    TCS=serialport(['COM' num2str(COMport)],115200,'Timeout', 1);
    disp('Done');
    writeline(TCS,'F'); 
    bl_str=sprintf('N%i',baseline_temp*10);
    writeline(TCS,bl_str);
end
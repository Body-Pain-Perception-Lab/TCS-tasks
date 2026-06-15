%Function used to transmit basic stimulation settings to the TCS
%stimulator.
%Author: Arthur S. Courtin
%License: MIT

function TCS_set_simple_stimulation_parameters(TCS,active_zones,target_temp,duration,speed,return_speed)
%TCS: a TCS serial object
%active_zones: a vector containing the indices of all active zones
%target_temp:target temperature in C
%duration in s
%speeds in C/s

    z='00000';
    for idx=active_zones
        z(idx)='1';
    end
    writeline(TCS,['S' z]);
    
    str=sprintf('C0%03i',round(target_temp*10));
    writeline(TCS,str)
    
    str=sprintf('D0%05i',round(duration*1000));
    writeline(TCS,str)
    
    str=sprintf('V0%04i',round(speed*10));
    writeline(TCS,str)
    
    str=sprintf('R0%04i',round(return_speed*10));
    writeline(TCS,str)
end
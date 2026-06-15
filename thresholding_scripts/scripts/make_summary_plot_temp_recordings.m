%Function used to pot the temperatures recorded during stimulation.
%This plot can be used for quick quality control. 
%Author: Arthur S. Courtin
%License: MIT 

function make_summary_plot_temp_recordings(PM)
    close all

    figure('units','normalized','outerposition',[0 0 1 1])

    TR=PM.temperature;
    
    hold on
    for idx=1:length(TR)
        tr=cell2mat(TR(idx));
        plot(tr(:,1),tr(:,2:end));
    end
    hold off
    xlabel('Time (s)')
    ylabel('Temperature (°C)')
end
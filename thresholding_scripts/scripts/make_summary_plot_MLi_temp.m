%Function used to create summary plot for the method of limits thresholding
%results. This image can be used for quick quality control.
%Author: Arthur S. Courtin
%License: MIT

function make_summary_plot_MLi_temp(results)
    close all

    figure('units','normalized','outerposition',[0 0 1 1])

    subplot(1,3,1)
    for idx=1:3
        t=cell2mat(results.cdt.training.temp(idx));
        plot(t(:,1),t(:,2:end))
        
        t=cell2mat(results.cdt.test.temp(idx));
        plot(t(:,1),t(:,2:end))
    end
    title('CDT')

    subplot(1,3,2)
    for idx=1:3
        t=cell2mat(results.wdt.training.temp(idx));
        plot(t(:,1),t(:,2:end))
        
        t=cell2mat(results.wdt.test.temp(idx));
        plot(t(:,1),t(:,2:end))
    end
    title('WDT')

    subplot(1,3,3)
    for idx=1:3
        t=cell2mat(results.hpt.training.temp(idx));
        plot(t(:,1),t(:,2:end))
        
        t=cell2mat(results.hpt.test.temp(idx));
        plot(t(:,1),t(:,2:end))
    end
    title('HPT')
end
%Function used to create summary plot for the method of limits thresholding
%results. This image can be used for quick quality control.
%Author: Arthur S. Courtin
%License: MIT

function make_summary_plot_MLi(results,params)
    close all

    figure('units','normalized','outerposition',[0 0 1 1])

    subplot(1,3,1)
    plot(1:3,params.baseline-results.cdt.training.value,'k*') 
    hold on
    plot(1:3,params.baseline-results.cdt.test.value,'ko') 
    hold off
    xlim([0 4])
    ylim([0 30])
    xlabel('Trial')
    ylabel('Threshold')
    legend('train','test')
    title('CDT')

    subplot(1,3,2)
    plot(1:3,results.wdt.training.value-params.baseline,'k*') 
    hold on
    plot(1:3,results.wdt.test.value-params.baseline,'ko') 
    hold off
    xlim([0 4])
    ylim([0 30])
    xlabel('Trial')
    ylabel('Threshold')
    legend('train','test')
    title('WDT')

    subplot(1,3,3)
    plot(1:3,results.hpt.training.value-params.baseline,'k*') 
    hold on
    plot(1:3,results.hpt.test.value-params.baseline,'ko') 
    hold off
    xlim([0 4])
    ylim([0 30])
    xlabel('Trial')
    ylabel('Threshold')
    legend('train','test')
    title('HPT')
end
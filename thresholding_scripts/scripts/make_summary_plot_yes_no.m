%Function used to make a summary plot of the YN thresholding results. This
%figure can be used for quick quality control.
%Author: Arthur S. Courtin
%License: MIT

function make_summary_plot_yes_no(PM, n)
    close all
    
    figure('units','normalized','outerposition',[0 0 1 1])

    subplot(3,2,1:2)
    hold on
    for x=unique(PM.x)
        if sum(PM.x(1:end-1)==x)>0        
            plot(x,betainv(0.5,1+sum(PM.response(PM.x(1:end-1)==x)),1+sum(abs(1-PM.response(PM.x(1:end-1)==x)))),'k.')
            plot([x x],betainv([0.025 0.975],1+sum(PM.response(PM.x(1:end-1)==x)),1+sum(abs(1-PM.response(PM.x(1:end-1)==x)))),'k')
        end
    end
    plot(min(PM.x)-1:.1:max(PM.x)+1,normcdf(min(PM.x)-1:.1:max(PM.x)+1,PM.threshold(end),1/10^(PM.slope(end))),'k:')
    hold off
    xlim([0 max(PM.x)+1])
    ylim([0 1])
    ylabel('P(detect)')
    title('Performance')
    xlabel('Temperature \delta (°C)')
    
    subplot(3,2,3)
    hold on
    plot(PM.threshold,'k')
    plot(PM.threshold+2*PM.seThreshold,'k:')
    plot(PM.threshold-2*PM.seThreshold,'k:')
    for idx=1:length(PM.response)
        plot(idx,PM.x(idx),'ko')
        if PM.response(idx)
            plot(idx,PM.x(idx),'k*')
        end
    end
    hold off
    xlim([0 n+1])
    ylim([min(PM.x)-1 max(PM.x)+1])
    title('\alpha estimate')
    xlabel('Trial')

    subplot(3,2,4)
    hold on
    plot(PM.slope,'k')
    plot(PM.slope+2*PM.seSlope,'k:')
    plot(PM.slope-2*PM.seSlope,'k:')
    hold off
    xlim([0 n+1])
    ylim([min(PM.priorBetaRange) max(PM.priorBetaRange)])
    title('log10(\beta) estimate')
    xlabel('Trial')

    subplot(3,2,5)
    hold on
    plot(PM.guess,'k')
    plot(PM.guess+2*PM.seGuess,'k:')
    plot(PM.guess-2*PM.seGuess,'k:')
    hold off
    xlim([0 n+1])
    ylim([min(PM.priorLambdaRange) max(PM.priorLambdaRange)])
    title('\gamma estimate')
    xlabel('Trial')

    subplot(3,2,6)
    hold on
    plot(PM.lapse,'k')
    plot(PM.lapse+2*PM.seLapse,'k:')
    plot(PM.lapse-2*PM.seLapse,'k:')
    hold off
    xlim([0 n+1])
    ylim([min(PM.priorLambdaRange) max(PM.priorLambdaRange)])
    title('\lambda estimate')
    xlabel('Trial')
end
%Function used to make a summary plot of the 2IFC thresholding results.
%This plot can be used for quick quality control. 
%Author: Arthur S. Courtin
%License: MIT

function make_summary_plot_performance_2ifc(PM, n)
    close all

    figure('units','normalized','outerposition',[0 0 1 1])

    subplot(3,2,1:2)
    l=length(PM.x)-1;
    x=round(PM.x(1:l),1);
    a=round(PM.active_interval(1:l));
    x(a==1)=-x(a==1);
    y=PM.response;
    y(a==1)=abs(1-y(a==1));
    u=unique(x);
    hold on
    for i=1:length(u)
        plot(u(i),betainv(0.5,1+sum(y(x==u(i))),1+sum(abs(1-y(x==u(i))))),'k.')
        plot([u(i) u(i)],betainv([0.025 0.975],1+sum(y(x==u(i))),1+sum(abs(1-y(x==u(i))))),'k')
    end
    plot([0 0],[0 1],'k--')
    hold off
    xlim([-1-max(PM.x) max(PM.x)+1])
    ylim([0 1])
    ylabel('P(response=right)')
    title('Performance - intervals')
    xlabel('Temperature \delta (°C; negative values correspond to first interval stimuli)')

    subplot(3,2,3)
    hold on
    for x=unique(PM.x)
        if sum(PM.x(1:end-1)==x)>0        
            plot(x,betainv(0.5,1+sum(PM.response(PM.x(1:end-1)==x)),1+sum(abs(1-PM.response(PM.x(1:end-1)==x)))),'k.')
            plot([x x],betainv([0.025 0.975],1+sum(PM.response(PM.x(1:end-1)==x)),1+sum(abs(1-PM.response(PM.x(1:end-1)==x)))),'k')
        end
    end
    x=abs(min(PM.x)-1:.1:max(PM.x)+1);
    plot(x,0.5+(1-0.5-PM.lapse(end))*(1 - 2.^(-(x./PM.threshold(end)).^(10.^PM.slope(end)))),'k:')
    hold off
    xlim([0 max(PM.x)+1])
    ylim([0 1])
    ylabel('P(correct)')
    title('Performance - aggregated')
    xlabel('Temperature \delta (°C)')

    subplot(3,2,4)
    hold on
    plot(PM.threshold,'k')
    plot(PM.threshold+2*PM.seThreshold,'k:')
    plot(PM.threshold-2*PM.seThreshold,'k:')
    for idx=1:length(PM.x)-1
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

    subplot(3,2,5)
    hold on
    plot(PM.slope,'k')
    plot(PM.slope+2*PM.seSlope,'k:')
    plot(PM.slope-2*PM.seSlope,'k:')
    hold off
    xlim([0 n+1])
    ylim([floor(min(PM.priorBetaRange)) ceil(max(PM.priorBetaRange))])
    title('log10(\beta) estimate')
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
%Function used to trigger stimulation by the TCS and record temperature at
%the surface of the probe throughout.
%Author: Arthur S. Courtin
%License: MIT

function tp=stimulate_and_record_temperature(TCS,recordTime,plot_temp)
    tp=nan(1000,6);
    timepoint=1;        
    flush(TCS);
    time_sampled=0;
    tic;
    launched_stim=0;
    while toc < (recordTime+0.5)
        if (toc-time_sampled)>=0.01
            time_sampled = toc';
            if launched_stim==0
                if time_sampled>0.5
                    writeline(TCS,'L');
                    launched_stim=1;
                end
            end
            writeline(TCS,'E');
            data=read(TCS, 24, 'char');     
            if size( data, 2 ) > 23
                temperatures( 1 ) = str2num( data(5:8) ) / 10;
                temperatures( 2 ) = str2num( data(9:12) ) / 10;
                temperatures( 3 ) = str2num( data(13:16) ) / 10;
                temperatures( 4 ) = str2num( data(17:20) ) / 10;
                temperatures( 5 ) = str2num( data(21:24) ) / 10;
                tp(timepoint,1) = time_sampled-0.5;
                tp(timepoint,2:6) = temperatures;            
                timepoint = timepoint + 1; % update counter
            else
            end
        end
    end

    tp=tp(~isnan(tp(:,1)),:);

    if plot_temp==1
        plot(tp(1:end,1),tp(1:end,2:end),'--');
    end
end
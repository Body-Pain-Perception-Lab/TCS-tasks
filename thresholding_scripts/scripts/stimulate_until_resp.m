%Function used to trigger stimulation by the TCS. The stimulation lasts
%until the participant encodes a response.
%Author: Arthur S. Courtin
%License: MIT

function tp=stimulate_until_resp(TCS,delay,speed,return_speed,baseline_temp,max,response_type,plot_temp)
    recordTime=abs(max-baseline_temp)/speed;  
    tp=nan((recordTime+delay)*100,6);

    writeline(TCS,'S11111');

    str=sprintf('C0%03i',round(max*10));
    writeline(TCS,str)
    
    str=sprintf('D0%05i',round(recordTime*1000));
    writeline(TCS,str)
    
    str=sprintf('V0%04i',round(speed*10));
    writeline(TCS,str)
    
    str=sprintf('R0%04i',round(return_speed*10));
    writeline(TCS,str)

    timepoint=1;        
    flush(TCS);
    time_sampled=0;
    tic;
    launched_stim=0;
    switch response_type
        case 'keyboard'
            while toc < (recordTime+delay)
                if (toc-time_sampled)>=0.01
                    time_sampled = toc';
        
                    if launched_stim==0
                        if time_sampled>delay
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
        
                    [~, ~, keys.KeyCode] = KbCheck;
                    if sum(keys.KeyCode) > 0
                        break
                    end
                end
            end
    
    writeline(TCS,'A')
    
    bl_str=sprintf('N%i',baseline_temp*10);
    writeline(TCS,bl_str);

    tp=tp(~isnan(tp(:,1)),:);

    if plot_temp==1
        plot(tp(1:end,1),tp(1:end,2:end),'--');
    end
end
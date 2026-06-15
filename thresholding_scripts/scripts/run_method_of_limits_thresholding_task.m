%Function used to run the methods of limits thresholding task.
%Author: Arthur S. Courtin
%License: MIT 

function [results,params]=run_method_of_limits_thresholding_task(TCS,language,response_type,baseline,plot_stimulus,stimulate,practice)
    close all
    
    params=set_params_method_of_limits_thresholding_task(language,baseline);
    results=[];
    
    %% Experimental run
    Screen('Preference', 'SkipSyncTests', 1);
    
    % Make sure we are using Psychtoolbox-3:
    AssertOpenGL;
    
    try    
        KbName('UnifyKeyNames');
        keys.Escape = KbName('ESCAPE');
    
        %First call of response collecting function to avoid lag
        if strcmp(response_type,'mouse')
            GetClicks([],[],[],0); 
        end
        KbCheck;
    
        %Disable input to matlab
        ListenChar(2);
    
        %Make psychtoolbox not complain all the time
        olddebuglevel=Screen('Preference', 'VisualDebuglevel', 3);
    
        %Choose monitor if there is more than 1
        screens=Screen('Screens');
        screenNumber=max(screens);
        
        %open the Window
        [expWin,rect]=Screen('OpenWindow',screenNumber,params.background_color);%,[100,100,1900,1100]);
    
        %get the center of the window
        [mx, my] = RectCenter(rect);
    
        HideCursor;
    
        Screen('TextSize', expWin, 35);
        
        [LC,RC,LCc,RCc]=make_response_type_images(expWin,response_type,params.background_color,params.text_color,params.middle_color);
        
        if practice
            %% general instructions practice
            DrawFormattedText(expWin, params.general_instructions_practice, 'center', 'center',params.text_color);
            t_instruction_onset = Screen('Flip', expWin);
            WaitSecs(params.screen_refresh_lag);
            [left,up,rt,break_signal]=collect_binary_response(expWin,t_instruction_onset,response_type,inf);
            
            if up==1
            elseif break_signal==1
            else
                DrawFormattedText(expWin, params.wait_instruction, 'center', 'center',params.text_color);
                t_instruction_onset = Screen('Flip', expWin);    
                pause(60)
        
                DrawFormattedText(expWin, params.general_instructions_practice, 'center', 'center',params.text_color);
                t_instruction_onset = Screen('Flip', expWin);
                WaitSecs(params.screen_refresh_lag);
                [left,up,rt,break_signal]=collect_binary_response(expWin,t_instruction_onset,response_type,inf);
        
                if up==1
                else
                    DrawFormattedText(expWin, params.wait_instruction, 'center', 'center',params.text_color);
                    t_instruction_onset = Screen('Flip', expWin);    
                    pause(60)
                end
            end
            
            %% cdt training
            if break_signal
            else
                DrawFormattedText(expWin, params.cdt_instruction_practice, 'center', 'center',params.text_color);
                t_instruction_onset = Screen('Flip', expWin);
                WaitSecs(params.screen_refresh_lag);
                [left,up,rt,break_signal]=collect_binary_response(expWin,t_instruction_onset,response_type,inf);                  
                for idx=1:params.n_practice       
                    [~, ~, keys.KeyCode] = KbCheck;
                    if keys.KeyCode(keys.Escape) == 1
                        break_signal=1;
                        break
                    end 
            
                    DrawFormattedText(expWin, params.inter_trial_text, 'center', 'center',params.text_color);
                    Screen('Flip', expWin);
            
                    WaitSecs(params.cdt.iti)
            
                    DrawFormattedText(expWin, params.cdt_question, 'center', 'center',params.text_color);
                    Screen('Flip', expWin);
                    WaitSecs(params.stim_delay)
            
                    if stimulate
                        pause(rand);
                        tp=stimulate_until_resp(TCS,params.stim_delay,params.speed,params.return,params.baseline,params.cdt.max,response_type,plot_stimulus);
                        results.cdt.training.value(idx)=min(mean(tp(:,2:end),2));
                        results.cdt.training.temp(idx)={tp};
                    end
                end    
            end
            %% wdt training
            if break_signal
            else
                DrawFormattedText(expWin, params.wdt_instruction_practice, 'center', 'center',params.text_color);
                t_instruction_onset = Screen('Flip', expWin);
                WaitSecs(params.screen_refresh_lag);
                [left,up,rt,break_signal]=collect_binary_response(expWin,t_instruction_onset,response_type,inf);   
        
               for idx=1:params.n_practice        
                    [~, ~, keys.KeyCode] = KbCheck;
                    if keys.KeyCode(keys.Escape) == 1
                        break_signal=1;
                        break
                    end 
                    DrawFormattedText(expWin, params.inter_trial_text, 'center', 'center',params.text_color);
                    Screen('Flip', expWin);
            
                    WaitSecs(params.wdt.iti)
            
                    DrawFormattedText(expWin, params.wdt_question, 'center', 'center',params.text_color);
                    Screen('Flip', expWin);
                    
                    WaitSecs(params.stim_delay)
            
                    if stimulate
                        pause(rand);
                        tp=stimulate_until_resp(TCS,params.stim_delay,params.speed,params.return,params.baseline,params.wdt.max,response_type,plot_stimulus);
                        results.wdt.training.value(idx)=max(mean(tp(:,2:end),2));
                        results.wdt.training.temp(idx)={tp};
                    end
                end
            end
            
            %% hpt training          
            if break_signal
            else
               DrawFormattedText(expWin, params.hpt_instruction_practice, 'center', 'center',params.text_color);
               t_instruction_onset = Screen('Flip', expWin);
               WaitSecs(params.screen_refresh_lag);
               [left,up,rt,break_signal]=collect_binary_response(expWin,t_instruction_onset,response_type,inf);   
               for idx=1:params.n_practice        
                    [~, ~, keys.KeyCode] = KbCheck;
                    if keys.KeyCode(keys.Escape) == 1
                        break_signal=1;
                        break
                    end 
                    
                    DrawFormattedText(expWin, params.inter_trial_text, 'center', 'center',params.text_color);
                    Screen('Flip', expWin);
            
                    WaitSecs(params.hpt.iti)
                    
                    DrawFormattedText(expWin, params.hpt_question, 'center', 'center',params.text_color);
                    Screen('Flip', expWin);
                    
                    WaitSecs(params.stim_delay)
            
                    if stimulate
                        pause(rand);
                        tp=stimulate_until_resp(TCS,params.stim_delay,params.speed,params.return,params.baseline,params.hpt.max,response_type,plot_stimulus);
                        results.hpt.training.value(idx)=max(mean(tp(:,2:end),2));
                        results.hpt.training.temp(idx)={tp};
                    end
                end
            end
        end
        %% general instructions test
        if up==1
        elseif break_signal==1
        else
            DrawFormattedText(expWin, params.general_instructions_test, 'center', 'center',params.text_color);
            t_instruction_onset = Screen('Flip', expWin);
            WaitSecs(params.screen_refresh_lag);
            [left,up,rt,break_signal]=collect_binary_response(expWin,t_instruction_onset,response_type,inf);
        
            DrawFormattedText(expWin, params.wait_instruction, 'center', 'center',params.text_color);
            t_instruction_onset = Screen('Flip', expWin);    
            pause(60)
    
            DrawFormattedText(expWin, params.general_instructions_test, 'center', 'center',params.text_color);
            t_instruction_onset = Screen('Flip', expWin);
            WaitSecs(params.screen_refresh_lag);
            [left,up,rt,break_signal]=collect_binary_response(expWin,t_instruction_onset,response_type,inf);
    
            if up==1
            else
                DrawFormattedText(expWin, params.wait_instruction, 'center', 'center',params.text_color);
                t_instruction_onset = Screen('Flip', expWin);    
                pause(60)
            end
        end
       
        %% cdt test
        if break_signal
        else
            DrawFormattedText(expWin, params.cdt_instruction_test, 'center', 'center',params.text_color);
            t_instruction_onset = Screen('Flip', expWin);
            WaitSecs(params.screen_refresh_lag);
            [left,up,rt,break_signal]=collect_binary_response(expWin,t_instruction_onset,response_type,inf);   
            for idx=1:params.n_test        
                [~, ~, keys.KeyCode] = KbCheck;
                if keys.KeyCode(keys.Escape) == 1
                    break_signal=1;
                    break
                end 
        
                DrawFormattedText(expWin, params.inter_trial_text, 'center', 'center',params.text_color);
                Screen('Flip', expWin);
        
                WaitSecs(params.cdt.iti)
        
                DrawFormattedText(expWin, params.cdt_question, 'center', 'center',params.text_color);
                Screen('Flip', expWin);
                
                WaitSecs(params.stim_delay)
                
                if stimulate
                    pause(rand);
                    tp=stimulate_until_resp(TCS,params.stim_delay,params.speed,params.return,params.baseline,params.cdt.max,response_type,plot_stimulus);
                    results.cdt.test.value(idx)=min(mean(tp(:,2:end),2));
                    results.cdt.test.temp(idx)={tp};
                end
            end    
        end
        %% wdt test
        if break_signal
        else    
            DrawFormattedText(expWin, params.wdt_instruction_test, 'center', 'center',params.text_color);
            t_instruction_onset = Screen('Flip', expWin);
            WaitSecs(params.screen_refresh_lag);
            [left,up,rt,break_signal]=collect_binary_response(expWin,t_instruction_onset,response_type,inf);   
           for idx=1:params.n_test        
                [~, ~, keys.KeyCode] = KbCheck;
                if keys.KeyCode(keys.Escape) == 1
                   break_signal=1;
                   break
                end 
        
                DrawFormattedText(expWin, params.inter_trial_text, 'center', 'center',params.text_color);
                Screen('Flip', expWin);
        
                WaitSecs(params.wdt.iti)
        
                DrawFormattedText(expWin, params.wdt_question, 'center', 'center',params.text_color);
                Screen('Flip', expWin);
                
                WaitSecs(params.stim_delay)
                
                if stimulate
                    pause(rand);
                    tp=stimulate_until_resp(TCS,params.stim_delay,params.speed,params.return,params.baseline,params.wdt.max,response_type,plot_stimulus);        
                    results.wdt.test.value(idx)=max(mean(tp(:,2:end),2));
                    results.wdt.test.temp(idx)={tp};
                end
            end
        end
        %% hpt test
        if break_signal
        else
            DrawFormattedText(expWin, params.hpt_instruction_test, 'center', 'center',params.text_color);
            t_instruction_onset = Screen('Flip', expWin);
            WaitSecs(params.screen_refresh_lag);
            [left,up,rt,break_signal]=collect_binary_response(expWin,t_instruction_onset,response_type,inf);   
            for idx=1:params.n_test        
                [~, ~, keys.KeyCode] = KbCheck;
                if keys.KeyCode(keys.Escape) == 1
                    break_signal=1;
                    break
                end 
                
                DrawFormattedText(expWin, params.inter_trial_text, 'center', 'center',params.text_color);
                Screen('Flip', expWin);
        
                WaitSecs(params.hpt.iti)
        
                DrawFormattedText(expWin, params.hpt_question, 'center', 'center',params.text_color);
                Screen('Flip', expWin);
                
                WaitSecs(params.stim_delay)
                
                if stimulate
                    pause(rand);
                    tp=stimulate_until_resp(TCS,params.stim_delay,params.speed,params.return,params.baseline,params.hpt.max,response_type,plot_stimulus);   
                    results.hpt.test.value(idx)=max(mean(tp(:,2:end),2));
                    results.hpt.test.temp(idx)={tp};
               end
            end
        end
        %%
        DrawFormattedText(expWin, params.end_of_task_text, 'center', 'center',params.text_color);
        Screen('Flip', expWin);
       
        %clean up before exit
        ShowCursor;
        sca;
        ListenChar(0);
        %return to olddebuglevel
        Screen('Preference', 'VisualDebuglevel', olddebuglevel);
    
    catch
        % This section is executed only in case an error happens in the
        % experiment code implemented between try and catch...
        ShowCursor;
        sca; %or sca
        ListenChar(0);
        Screen('Preference', 'VisualDebuglevel', olddebuglevel);
        %output the error message
        psychrethrow(psychlasterror);
    end

end
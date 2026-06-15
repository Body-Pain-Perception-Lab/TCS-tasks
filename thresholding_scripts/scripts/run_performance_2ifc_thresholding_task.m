%Function used to run the 2IFC thresholding task.
%Author: Arthur S. Courtin
%License: MIT

function [PM,params]=run_performance_2ifc_thresholding_task(TCS,type,language,response_type,baseline,probe,stimulate,plot_stimulus)

    close all
    
    params=set_params_performance_2ifc_thresholding_task(type,language,baseline,probe);
    
    %% Initialize adaptive method
    PM = PAL_AMPM_setupPM( ...
        'priorAlphaRange',[10^-2,params.par],...
        'priorBetaRange',params.pbr,...
        'priorLambdaRange',params.plr,...
        'priorGammaRange',0.5,...
        'stimRange',params.par,...
        'PF',@PAL_Weibull...
        );
    PM.rep=zeros(1,params.n);
    
    prior = ...
        PAL_pdfNormal(PM.priorAlphas,params.pam,params.pas).*...
        ones(size(PM.priorBetas)).*...
        ones(size(PM.priorGammas)).*...
        PAL_pdfNormal(log(2*PM.priorLambdas./(1-2*PM.priorLambdas)),params.plm_half_logit,params.pls_half_logit);
    
    prior=prior./sum(sum(sum(sum(prior))));
    
    PM = PAL_AMPM_setupPM(PM,'prior',prior);
    
    for idx=1:ceil((params.n)/6)
       active_zones((1:6)+(idx-1)*6)=[1 2 1 2 1 2];
       active_interval((1:6)+(idx-1)*6)=randsample([ones(1,3) ones(1,3)*2],6,false);
    end
    
    
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
        
        if stimulate
            TCS_set_simple_stimulation_parameters(TCS,1:5,params.baseline,params.duration,params.speed,params.return);
            tp=stimulate_and_record_temperature(TCS,params.record_time,0);
        end
    
        %Disable input to matlab
        ListenChar(2);
    
        %Make psychtoolbox not complain all the time
        olddebuglevel=Screen('Preference', 'VisualDebuglevel', 3);
    
        %Choose monitor if there is more than 1
        screens=Screen('Screens');
        screenNumber=max(screens);
        
        %open the Window
        [expWin,rect]=Screen('OpenWindow',screenNumber,params.background_color);
    
        %get the center of the window
        [mx, my] = RectCenter(rect);
    
        HideCursor;
    
        Screen('TextSize', expWin, 35);
        
        fixcross=make_fixation_cross(expWin,params.background_color,params.text_color);
        [LC,RC,LCc,RCc]=make_response_type_images(expWin,response_type,params.background_color,params.text_color,params.middle_color);
       
        DrawFormattedText(expWin, params.instruction_text, 'center', 'center',params.text_color);
        t_instruction_onset = Screen('Flip', expWin);
        WaitSecs(params.screen_refresh_lag);
        collect_binary_response(expWin,t_instruction_onset,response_type,inf);
    
        %data acquisition loop
        for trial=1:params.n
            %IT screen
            t_trial_start = Screen('Flip', expWin);
            
            %setting TCS for stimulation
            if stimulate
                target_delta_temperature = PM.xCurrent;
                
                if params.direction==1
                    if active_zones(trial)==1
                        TCS_set_simple_stimulation_parameters(TCS,[4 5],params.baseline+target_delta_temperature,params.duration,params.speed,params.return)
                    else
                        TCS_set_simple_stimulation_parameters(TCS,[1 2],params.baseline+target_delta_temperature,params.duration,params.speed,params.return)
                    end
                else
                    if active_zones(trial)==1
                        TCS_set_simple_stimulation_parameters(TCS,[4 5],params.baseline-target_delta_temperature,params.duration,params.speed,params.return)
                    else
                        TCS_set_simple_stimulation_parameters(TCS,[1 2],params.baseline-target_delta_temperature,params.duration,params.speed,params.return)
                    end
                end
            end
    
            [~, ~, keys.KeyCode] = KbCheck;
            if keys.KeyCode(keys.Escape) == 1
                break
            end        
    
            %Stimulation screen
            Screen('DrawTexture', expWin, fixcross, [],[mx/2-20 my-20 mx/2+20 my+20]);
            t_fixation_1 = Screen('Flip', expWin,t_trial_start+params.iti);
    
            WaitSecs('UntilTime',t_fixation_1+params.stim_delay);
            
            if stimulate && active_interval(trial)==1
                tp=stimulate_and_record_temperature(TCS,params.record_time,plot_stimulus);
    
                PM.temperature(trial)={tp};
                PM.active_zones(trial)=active_zones(trial);
                PM.active_interval(trial)=active_interval(trial);
            end
            
            Screen('DrawTexture', expWin, fixcross, [],[3*mx/2-20 my-20 3*mx/2+20 my+20]);
            t_fixation_2 = Screen('Flip', expWin,t_fixation_1+params.interval_duration);
    
            WaitSecs('UntilTime',t_fixation_2+params.stim_delay);
            
            if stimulate && active_interval(trial)==2
                tp=stimulate_and_record_temperature(TCS,params.record_time,plot_stimulus);
    
                PM.temperature(trial)={tp};
                PM.active_zones(trial)=active_zones(trial);
                PM.active_interval(trial)=active_interval(trial);
            end
            
            WaitSecs('UntilTime',t_fixation_2+params.interval_duration);        
            
            [~, ~, keys.KeyCode] = KbCheck;
            if keys.KeyCode(keys.Escape) == 1
                break
            end   
            
            %Question
            DrawFormattedText(expWin,params.left_choice, mx-250,my+200,params.text_color);
            DrawFormattedText(expWin,params.right_choice, mx+180,my+200,params.text_color);
            Screen('DrawTexture', expWin, LC, [], [mx-320,my+220,mx-120,my+420]);
            Screen('DrawTexture', expWin, RC, [], [mx+120,my+220,mx+320,my+420]);
    
            DrawFormattedText(expWin, params.question, 'center', 'center',params.text_color);
            
            t_question_onset = Screen('Flip', expWin);
    
            [~, ~, keys.KeyCode] = KbCheck;
            if keys.KeyCode(keys.Escape) == 1
                break
            end
    
            %Question and response
            repeat_signal=0;
            WaitSecs(params.screen_refresh_lag);
            [left,up,rt,break_signal]=collect_binary_response(expWin,t_question_onset,response_type,params.question_time_out);
            if break_signal==1
                break   
            end
            if isnan(rt)
                DrawFormattedText(expWin, params.too_slow_text, 'center', 'center',params.text_color);
                left=NaN;
                rt=NaN;
                correct=NaN;
                repeat_signal=1;
                PM.rep(length(PM.x))=PM.rep(length(PM.x))+1;
            elseif left==1
                DrawFormattedText(expWin,params.left_choice, mx-250,my+200,params.middle_color);
                DrawFormattedText(expWin,params.right_choice, mx+180,my+200,params.text_color);
                Screen('DrawTexture', expWin, LCc, [], [mx-320,my+220,mx-120,my+420]);
                Screen('DrawTexture', expWin, RC, [], [mx+120,my+220,mx+320,my+420]);
                DrawFormattedText(expWin, params.question, 'center', 'center',params.text_color);
                correct=active_interval(trial)==1;
            else
                DrawFormattedText(expWin,params.left_choice, mx-250,my+200,params.text_color);
                DrawFormattedText(expWin,params.right_choice, mx+180,my+200,params.middle_color);
                Screen('DrawTexture', expWin, LC, [], [mx-320,my+220,mx-120,my+420]);
                Screen('DrawTexture', expWin, RCc, [], [mx+120,my+220,mx+320,my+420]);
                DrawFormattedText(expWin, params.question, 'center', 'center',params.text_color);
                correct=active_interval(trial)==2;
            end
            
            PM.rt(trial)=rt;
    
            [~, ~, keys.KeyCode] = KbCheck;
            if keys.KeyCode(keys.Escape) == 1
                break
            end
    
            Screen('Flip', expWin);
            WaitSecs(1);
            
            if repeat_signal==0
                PM=PAL_AMPM_updatePM(PM,correct);
            end
        end
    
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
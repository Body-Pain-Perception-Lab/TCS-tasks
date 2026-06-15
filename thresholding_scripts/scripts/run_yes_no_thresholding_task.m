%Function used to run the YN thresholding task.
%Author: Arthur S. Courtin
%License: MIT

function [params,PM,UD]=run_yes_no_thresholding_task(TCS,type,language,response_type,baseline,probe,stimulate,plot_stimulus)
    close all
    
    params=set_params_yes_no_thresholding_task(type,language,baseline,probe);
    
    %% Initialize adaptive method
    UD=[];
    if  params.n_up_down>0
        UD=PAL_AMUD_setupUD( ...
            'up',1, ...
            'down',1, ...
            'stepSizeUp',2, ...
            'stepSizeDown',1, ...
            'startValue',params.pam, ...
            'xMax',max(params.par), ...
            'xMin',0 ...
            );
        UD.rep=zeros(1,params.n_up_down);
    end
    
    PM = PAL_AMPM_setupPM( ...
        'priorAlphaRange',params.par,...
        'priorBetaRange',params.pbr,...
        'priorLambdaRange',params.plr,...
        'priorGammaRange',params.pgr,...
        'stimRange',params.par,...
        'PF',@PAL_CumulativeNormal...
        );
    PM.rep=zeros(1,params.n);
    
    prior = ...
        PAL_pdfNormal(PM.priorAlphas,params.pam,params.pas).*...
        PAL_pdfNormal(log(10.^PM.priorBetas),params.pbm_log,params.pbs_log).*...
        PAL_pdfNormal(log(2*PM.priorGammas./(1-2*PM.priorGammas)),params.pgm_half_logit,params.pgs_half_logit).*...
        PAL_pdfNormal(log(2*PM.priorLambdas./(1-2*PM.priorLambdas)),params.plm_half_logit,params.pls_half_logit);
    
    prior=prior./sum(sum(sum(sum(prior))));
    
    PM = PAL_AMPM_setupPM(PM,'prior',prior);
    PM.catch_trial=params.catch_trial;
    
    for idx=1:ceil((params.n+params.n_up_down)/2)
       active_zones((1:2)+(idx-1)*2)=[1 2];
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
        TCS_set_simple_stimulation_parameters(TCS,1:5,params.baseline,params.duration,params.speed,params.return)
        tp=stimulate_and_record_temperature(TCS,params.record_time,0);
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
        for trial=1:(params.n+params.n_up_down)
            %IT screen
            t_trial_start = Screen('Flip', expWin);
            
            %setting TCS for stimulation
            if stimulate
                if trial>params.n_up_down
                    if params.catch_trial(trial-params.n_up_down)==1
                        PM.xCurrent=0;
                        PM.x(end)=0;
                    end
                    target_delta_temperature = PM.xCurrent;
                else
                    target_delta_temperature = UD.xCurrent;
                end
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
            Screen('DrawTexture', expWin, fixcross, [],[mx-20 my-20 mx+20 my+20]);
            t_fixation = Screen('Flip', expWin,t_trial_start+params.iti);
    
            stim_start=WaitSecs('UntilTime',t_fixation+params.stim_delay);
            
            if stimulate
                tp=stimulate_and_record_temperature(TCS,params.record_time,plot_stimulus);
    
                if trial>params.n_up_down
                    PM.temperature(trial-params.n_up_down)={tp};
                    PM.active_zones(trial-params.n_up_down)=active_zones(trial);
                else
                    UD.temperature(trial)={tp};
                    UD.active_zones(trial)=active_zones(trial);
                end
            end
    
            WaitSecs('UntilTime',stim_start+params.post_stimulus_wait+params.duration);
            
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
            [yes,up,rt,break_signal]=collect_binary_response(expWin,t_question_onset,response_type,params.question_time_out);
            if break_signal==1
                break   
            end
            if isnan(rt)
                DrawFormattedText(expWin, params.too_slow_text, 'center', 'center',params.text_color);
                yes=NaN;
                rt=NaN;
                repeat_signal=1;
                if trial>params.n_up_down
                    PM.rep(length(PM.x))=PM.rep(length(PM.x))+1;
                else
                    UD.rep(length(UD.x))=UD.rep(length(UD.x))+1;
                end
            elseif yes==1
                DrawFormattedText(expWin,params.left_choice, mx-250,my+200,params.middle_color);
                DrawFormattedText(expWin,params.right_choice, mx+180,my+200,params.text_color);
                Screen('DrawTexture', expWin, LCc, [], [mx-320,my+220,mx-120,my+420]);
                Screen('DrawTexture', expWin, RC, [], [mx+120,my+220,mx+320,my+420]);
                DrawFormattedText(expWin, params.question, 'center', 'center',params.text_color);
            else
                DrawFormattedText(expWin,params.left_choice, mx-250,my+200,params.text_color);
                DrawFormattedText(expWin,params.right_choice, mx+180,my+200,params.middle_color);
                Screen('DrawTexture', expWin, LC, [], [mx-320,my+220,mx-120,my+420]);
                Screen('DrawTexture', expWin, RCc, [], [mx+120,my+220,mx+320,my+420]);
                DrawFormattedText(expWin, params.question, 'center', 'center',params.text_color);
            end
            
            if trial>params.n_up_down
                PM.rt(trial-params.n_up_down)=rt;
            else
                UD.rt(trial)=rt;
            end
    
            [~, ~, keys.KeyCode] = KbCheck;
            if keys.KeyCode(keys.Escape) == 1
                break
            end
    
            Screen('Flip', expWin);
            WaitSecs(1);
            
            if repeat_signal==0
                if trial>params.n_up_down
                    PM=PAL_AMPM_updatePM(PM,yes);
                else
                    UD=PAL_AMUD_updateUD(UD,yes);
                end
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
%Function used to collect binary responses with a variety of apparatus,
%within a Psychtoolbox experiment.
%Author: Arthur S. Courtin
%License: MIT

function [left,up,rt,break_signal]=collect_binary_response(expWin,t_question_onset,response_type,time_out)

break_signal=0;

switch response_type
    case 'mouse'
        WaitSecs(.1);
        [clicks,x,y,whichButton,clickSecs] = GetClicks(expWin, 0, [], t_question_onset+time_out);
        rt=clickSecs-t_question_onset;        
        left=whichButton==1;
        if whichButton==2
            break_signal=1;
            rt=NaN;
            left=NaN;
        elseif clicks==0
            rt=NaN;
            left=NaN;
        end

    case 'keyboard'
        KbName('UnifyKeyNames');
        keys.Escape = KbName('ESCAPE');
        keys.Left = KbName('LeftArrow');
        keys.Right = KbName('RightArrow');
        keys.Up = KbName('UpArrow');
        keys.Down = KbName('DownArrow');

        t=GetSecs;
        left=NaN;
        up=NaN;
        rt=NaN;
        WaitSecs(.1);
        while (t_question_onset+time_out)>t
            WaitSecs(.001);
            t=GetSecs;
            [~, ~, keys.KeyCode] = KbCheck;
            if keys.KeyCode(keys.Escape) == 1
                break_signal=1;
                up=nan();
                left=nan();
                rt=nan();
            elseif keys.KeyCode(keys.Left) == 1
                left=1;
                up=nan();
                rt=t-t_question_onset;        
                t=inf;
            elseif keys.KeyCode(keys.Right) == 1
                left=0;
                up=nan();
                rt=t-t_question_onset;        
                t=inf;
            elseif keys.KeyCode(keys.Up) == 1
                left=nan();
                up=1;
                rt=t-t_question_onset;                
                t=inf;
            elseif keys.KeyCode(keys.Down) == 1
                left=nan();
                up=0;
                rt=t-t_question_onset;        
                t=inf;
            end
        end
end

end
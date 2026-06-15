%Function used to set the parameters of the 2IFC thresholding task.
%Author: Arthur S. Courtin
%License: MIT

function params=set_params_performance_2ifc_thresholding_task(type,language,baseline,probe)

    params.pbr=-0.5:0.1:1.5;
    params.plr=10^-10:0.02:0.2;
    params.plm_half_logit=-3.97;
    params.pls_half_logit=1.69;
    
    params.baseline=baseline;
    params.iti=4;
    params.stim_delay=0.5;
    params.interval_duration=5;
    params.question_time_out=10;
    params.screen_refresh_lag=0.1;
    
    params.duration=2;
    params.record_time=params.duration+1;
    switch probe
        case 't03'
            params.speed=300;
        case 't06'
            params.speed=50;
        case 't11'
            params.speed=100;
    end
    params.return=1;
    
    params.middle_color=[60 60 160];
    params.background_color =[15 15 40];
    params.text_color=[200 200 240];
    
    params.save_summary_plot=1;
    
    params.start=5;
    params.step=2;
    
    params.n=30;
    
    switch type
        case 'CDT'
            params.direction=0;
            modality_idx=1;
            if (baseline-20)>10
                params.par=0.2:0.2:10;
            else
                params.par=0.2:0.2:(params.baseline-20);
            end
            params.pam=1;
            params.pas=5;
        case 'WDT'
            params.direction=1;
            modality_idx=2;
            if (42-baseline)>10
                params.par=0.2:0.2:10;
            else
                params.par=0.2:0.2:(42-params.baseline);
            end
            params.pam=2;
            params.pas=5;
    end
    
    switch language
        case 'FR'
            params.left_choice='gauche';
            params.right_choice='droite';
            params.too_slow_text='Trop lent!';
            modality={...
                'froid',...
                'chaud'...
                };
            params.instruction_text=[...
                'Nous allons maintenant tester votre sensibilité au ',char(modality(modality_idx)),'.\n\n\n',...
                'Pour ce faire, nous allons utiliser une série d´essais.\n',...
                'Chaque essai sera divisé en deux temps, indiqué par la présence \n d´une croix dans la moitié gauche ou droite de l´écran.\n',...
                'Au cours de chaque essai, nous allons chauffer et refroidir votre peau.\n',...
                'Votre tâche est de déterminer quand la stimulation était la plus ',char(modality(modality_idx)),'e (croix à gauche/droite).\n',...
                'Vous devez donner votre réponse en pressant le boutton correspondant \n à l´emplacement de la croix au moment de la stimulation (←/→).\n\n',...
                'Vous devez donner une réponse après chaque essai, même si vous n êtes pas certain.e.\n\n\n'...
                'Si vous avez des questions, vous pouvez les poser à l´expèrimentateur maintenant.\n',...
                'Si pas, prévenez l´expérimentateur quand vous êtes prêt.e. à commencer.'...
                ];       
            params.question=[...
                'Dans quelle partie de l´écran se trouvait la croix quand vous avez percu le plus de ',char(modality(modality_idx)),'?'...
                ];
            params.end_of_task_text='Fin de la tâche';
        case 'EN'
            params.left_choice='left';
            params.right_choice='right';
            params.too_slow_text='Too slow!';
            modality={...
                'cold',...
                'warm',...
                };
            params.instruction_text=[...
                'We will now test your sensitivity to ',char(modality(modality_idx)),'.\n\n\n',...
                'To do so, we will use a series of trials.\n',...
                'Each trial will be separated into two time periods, \n indicated by the presence of a cross in the left or right half of the screen.\n',...
                'During each trial, we will heat up and cool down your skin.\n',...
                'Your task will be to determine when the stimulus was the ',char(modality(modality_idx)),'est (cross in left/right).\n',...
                'You must provide your response using the corresponding button (←/→).\n',...
                'You must always give an answer, even when you are not sure.\n\n\n',...
                'If you have questions, you can ask them to the experimenter now.\n'...
                'If not, let the experimenter know that you are ready.'...
                ];
            params.question=[...
                'In which part of the screen was the cross when you felt more',char(modality(modality_idx)),'?'...
                ];
            params.end_of_task_text='End of task';
    end

end
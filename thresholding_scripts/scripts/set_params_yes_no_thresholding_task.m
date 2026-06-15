%Function used to cset the parameters of the YN thresholding task.
%Author: Arthur S. Courtin
%License: MIT
function params=set_params_yes_no_thresholding_task(type,language,baseline,probe)

    params.pbr=-1.5:0.1:1.5;
    params.pgr=10^-10:0.02:0.2;
    params.plr=params.pgr;
    
    params.pgm_half_logit=-3.05;
    params.pgs_half_logit=1.15;
    params.plm_half_logit=-3.86;
    params.pls_half_logit=1.53;
    
    params.baseline=baseline;
    params.stim_delay=0.5;
    params.post_stimulus_wait=1;
    params.question_time_out=10;
    params.screen_refresh_lag=0.1;
    
    params.duration=2;
    params.record_time=params.duration+params.post_stimulus_wait;
    switch probe
        case 't03'
            params.speed=300;
        case 't06'
            params.speed=50;
        case 't11'
            params.speed=100;
    end
    
    params.middle_color=[60 60 160];
    params.background_color =[15 15 40];
    params.text_color=[200 200 240];
    
    params.save_summary_plot=1;
    switch type
        case 'CDT'
            params.return=1;
            params.direction=0;
            params.par=0:0.2:(params.baseline-15);
            params.n_up_down=0;
            params.n=30;
            params.catch_trial=[randsample([ones(1,3),zeros(1,7)],10,false) randsample([ones(1,3),zeros(1,7)],10,false) randsample([ones(1,3),zeros(1,7)],10,false)];
            question_idx=1;
            modality_idx=1;
            params.pam=1.97;
            params.pas=2.09;
            params.pbm_log=-0.189;
            params.pbs_log=0.956;
            params.iti=4;
        case 'WDT'
            params.return=1;
            params.direction=1;
            params.par=0:0.2:(45-params.baseline);
            params.n_up_down=0;
            params.n=30;
            params.catch_trial=[randsample([ones(1,3),zeros(1,7)],10,false) randsample([ones(1,3),zeros(1,7)],10,false) randsample([ones(1,3),zeros(1,7)],10,false)];
            question_idx=2;        
            modality_idx=2;
            params.pam=6.18;
            params.pas=3.94;
            params.pbm_log=-0.792;
            params.pbs_log=0.859;
            params.iti=4;
        case 'CPT'
            params.return=params.speed;
            params.direction=0;
            params.par=0:.5:baseline;
            params.n_up_down=10;
            params.n=30;
            params.catch_trial=zeros(1,params.n);
            question_idx=3;
            modality_idx=3;
            params.pam=26.1;
            params.pas=11.3;
            params.pbm_log=-1.44;
            params.pbs_log=0.533;
            params.iti=4;
        case 'HPT'
            params.return=params.speed;
            params.direction=1;
            params.par=0:.5:abs(50-baseline);
            params.n_up_down=10;
            params.n=30;
            params.catch_trial=zeros(1,params.n);
            question_idx=3;
            modality_idx=4;
            params.pam=15.4;
            params.pas=3.06;
            params.pbm_log=0;
            params.pbs_log=0.809;
            params.iti=4;
    end
    
    switch language
        case 'FR'
            params.left_choice='OUI';
            params.right_choice='NON';
            params.too_slow_text='Trop lent!';
            modality={...
                'froid',...
                'chaud',...
                'froid douloureux',...
                'chaud douloureux',...
                };
            params.instruction_text=[...
                'Nous allons maintenant tester votre sensibilité au ',char(modality(modality_idx)),'.\n\n\n',...
                'Pour ce faire, nous allons utiliser une série d´essais.\n',...
                'Au cours de chaque essai, nous allons chauffer et/ou refroidir votre peau\n ou bien la garder à une température constante.\n',...
                'Après chaque stimulus, nous vous demanderons si vous avez senti du ',char(modality(modality_idx)),...
                '.\n Vous devez donner votre réponse (OUI/NON) en pressant le boutton correspondant (←/→).\n',...
                'Vous devez donner une réponse après chaque stimulus, même si vous n´êtes pas certain.e.\n\n\n'...
                'Si vous avez des questions, vous pouvez les poser à l´expèrimentateur.\n',...
                'Si pas, prévenez l´expérimentateur quand vous êtes prêt.e. à commencer.'...
                ];       
            question={...
                'Avez-vous senti un refroidissement?',...
                'Avez-vous senti un échauffement?',...
                'Avez-vous ressenti du brûlant/piquant/douloureux?'...
                };
            params.question=char(question(question_idx));
            params.end_of_task_text='Fin de la tâche';
        case 'EN'
            params.left_choice='YES';
            params.right_choice='NO';
            params.too_slow_text='Too slow!';
            modality={...
                'cold',...
                'warm',...
                'cold pain',...
                'heat pain',...
                };
            params.instruction_text=[...
                'We will now test your sensitivity to ',char(modality(modality_idx)),'.\n\n\n',...
                'To do so, we will give you a serie of stimulations.\n',...
                'During each trial, we will heat and/or cool your skin \n or keep it at a constant temperature.',...
                'After each stimulus, we will ask you if you felt ',char(modality(modality_idx)),...
                '.\n You must provide your response (YES/NO) using the corresponding button (←/→).\n',...
                'You must always give an answer, even when you are not sure.\n\n\n',...
                'If you have questions, you can ask them to the experimenter now.\n'...
                'If not, press any button to start.'...
                ];
            question={...
                'Did you feel a cooling',...
                'Did you feel a warming?',...
                'Did you feel a burning/pricking/aching/painful sensation?'...
                };
            params.question=char(question(question_idx));
            params.end_of_task_text='End of task';
        case 'SW' %the text needs to be translated
            params.left_choice='YES';
            params.right_choice='NO';
            params.too_slow_text='Too slow!';
            modality={...
                'cold',...
                'warm',...
                'cold pain',...
                'heat pain',...
                };
            params.instruction_text=[...
                'We will now test your sensitivity to ',char(modality(modality_idx)),'.\n\n\n',...
                'To do so, we will give you a serie of stimulations.\n',...
                'During each trial, we will heat and/or cool your skin \n or keep it at a constant temperature.',...
                'After each stimulus, we will ask you if you felt ',char(modality(modality_idx)),...
                '.\n You must provide your response (YES/NO) using the corresponding button (←/→).\n',...
                'You must always give an answer, even when you are not sure.\n\n\n',...
                'If you have questions, you can ask them to the experimenter now.\n'...
                'If not, press any button to start.'...
                ];
            question={...
                'Did you feel a cooling',...
                'Did you feel a warming?',...
                'Did you feel a burning/pricking/aching/painful sensation?'...
                };
            params.question=char(question(question_idx));
            params.end_of_task_text='End of task';
    end

end
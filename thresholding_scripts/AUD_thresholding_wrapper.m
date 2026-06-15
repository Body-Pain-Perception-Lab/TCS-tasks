%Wrapper function to run all types of thresholds in one site 
%Author: Arthur S. Courtin
%License: MIT (see LICENSE file) 

function AUD_thresholding_wrapper(task_type)
   
    close all

    % if no input, run all
    if ~exist("task_type","var")
        task_type = 'all';
    end
    
    %define which tasks to run
    switch task_type
        case 'limits_all'
            run_limits = 1;
            run_cdt_yn = 0;
            run_wdt_yn = 0;            
            run_hpt_yn = 0;
            run_cdt_2ifc = 0;
            run_wdt_2ifc = 0;
        case 'yes_no_cdt'
            run_limits = 0;
            run_cdt_yn = 1;
            run_wdt_yn = 0;            
            run_hpt_yn = 0;
            run_cdt_2ifc = 0;
            run_wdt_2ifc = 0;
        case 'yes_no_wdt'
            run_limits = 0;
            run_cdt_yn = 0;
            run_wdt_yn = 1;            
            run_hpt_yn = 0;
            run_cdt_2ifc = 0;
            run_wdt_2ifc = 0;
        case 'yes_no_hpt'
            run_limits = 0;
            run_cdt_yn = 0;
            run_wdt_yn = 0;            
            run_hpt_yn = 1;
            run_cdt_2ifc = 0;
            run_wdt_2ifc = 0;     
        case 'yes_no_all'
            run_limits = 0;
            run_cdt_yn = 1;
            run_wdt_yn = 1;            
            run_hpt_yn = 1;
            run_cdt_2ifc = 0;
            run_wdt_2ifc = 0;
        case '2ifc_cdt'
            run_limits = 0;
            run_cdt_yn = 0;
            run_wdt_yn = 0;            
            run_hpt_yn = 0;
            run_cdt_2ifc = 1;
            run_wdt_2ifc = 0;
        case '2ifc_wdt'
            run_limits = 0;
            run_cdt_yn = 0;
            run_wdt_yn = 0;            
            run_hpt_yn = 0;
            run_cdt_2ifc = 0;
            run_wdt_2ifc = 1;
        case '2ifc_all'
            run_limits = 0;
            run_cdt_yn = 0;
            run_wdt_yn = 0;            
            run_hpt_yn = 0;
            run_cdt_2ifc = 1;
            run_wdt_2ifc = 1;
        case 'all'
            run_limits = 1;
            run_cdt_yn = 1;
            run_wdt_yn = 1;            
            run_hpt_yn = 1;
            run_cdt_2ifc = 1;
            run_wdt_2ifc = 1;
    end
    
    plot_stimulus=0;
    language='FR';
    response_type='keyboard'; %can be either 'mouse' or 'keyboard'
    probe='t06';

    if ~exist([cd '\data'],'dir')
        mkdir([cd '\data'])
    else
    end
    addpath(genpath([cd '\scripts\']));
    
    %% Collect participant code
    session_info = collect_aud_session_info();

    stimulate=str2num(char(session_info(5)));
    baseline=str2num(char(session_info(6)));

    participant_name = sprintf('sub-%1s%03s', char(session_info(2)),char(session_info(1))); % Define subject
    
    block_dir=[cd '\data\',date,'\',participant_name,'\site_',char(session_info(3))];
    if ~exist(block_dir,'dir')
        mkdir(block_dir)
    else
    end
    
    save([block_dir, '\', participant_name,'_site-',char(session_info(3)),'_session_info.mat'],'session_info')
    
    %% Initialize TCS
    TCS=[];
    if stimulate
        TCS=TCS_initialize(str2num(char(session_info(4))),baseline);
    end
    
    %% Method of limits thresholds
    clear results   
    clear params
    if run_limits
        [results,params]=run_method_of_limits_thresholding_task(TCS,language,response_type,baseline,plot_stimulus,stimulate,1);

        save([block_dir, '\', participant_name,'_site-',char(session_info(3)),'_mli.mat'],'results','params')

        close all
        make_summary_plot_MLi(results, params)
        saveas(gcf,[block_dir, '\', participant_name,'_site-',char(session_info(3)),'_mli.png'])

        make_summary_plot_MLi_temp(results)
        saveas(gcf,[block_dir, '\', participant_name,'_site-',char(session_info(3)),'_mli_temp.png'])
        close all
    end    
    
    %% Yes-no cold detection 
    clear PM   
    clear params
    if run_cdt_yn
        [params,PM]=run_yes_no_thresholding_task(TCS,'CDT',language,response_type,baseline,probe,stimulate,plot_stimulus);

        save([block_dir, '\', participant_name,'_site-',char(session_info(3)),'_mle_yn_cdt.mat'],'PM','params', '-v7.3')

        close all
        make_summary_plot_yes_no(PM, params.n)
        saveas(gcf,[block_dir, '\', participant_name,'_site-',char(session_info(3)),'_yn_cdt.png'])
        close all
        make_summary_plot_temp_recordings(PM)
        saveas(gcf,[block_dir, '\', participant_name,'_site-',char(session_info(3)),'_yn_cdt_temp.png'])
        close all
    end  
    
    %% Yes-no warm detection 
    clear PM   
    clear params
    if run_wdt_yn
        [params,PM]=run_yes_no_thresholding_task(TCS,'WDT',language,response_type,baseline,probe,stimulate,plot_stimulus);

        save([block_dir, '\', participant_name,'_site-',char(session_info(3)),'_mle_yn_wdt.mat'],'PM','params', '-v7.3')

        close all
        make_summary_plot_yes_no(PM, params.n)
        saveas(gcf,[block_dir, '\', participant_name,'_site-',char(session_info(3)),'_yn_wdt.png'])
        close all
        make_summary_plot_temp_recordings(PM)
        saveas(gcf,[block_dir, '\', participant_name,'_site-',char(session_info(3)),'_yn_wdt_temp.png'])
        close all
    end  
    
    %% Yes-no heat pain 
    clear PM   
    clear params
    if run_hpt_yn
        [params,PM,UD]=run_yes_no_thresholding_task(TCS,'HPT',language,response_type,baseline,probe,stimulate,plot_stimulus);

        save([block_dir, '\', participant_name,'_site-',char(session_info(3)),'_mle_yn_hpt.mat'],'PM','UD','params', '-v7.3')

        close all
        make_summary_plot_yes_no(PM, params.n)
        saveas(gcf,[block_dir, '\', participant_name,'_site-',char(session_info(3)),'_yn_hpt.png'])
        close all
        make_summary_plot_temp_recordings(PM)
        saveas(gcf,[block_dir, '\', participant_name,'_site-',char(session_info(3)),'_yn_hpt_temp.png'])
        close all
    end  

    %% 2IFC cold detection 
    clear PM   
    clear params
    if run_cdt_2ifc
        [PM,params]=run_performance_2ifc_thresholding_task(TCS,'CDT',language,response_type,baseline,probe,stimulate,plot_stimulus);

        save([block_dir, '\', participant_name,'_site-',char(session_info(3)),'_mle_fc_cdt.mat'],'PM','params', '-v7.3')
        
        close all
        make_summary_plot_performance_2ifc(PM, params.n)
        saveas(gcf,[block_dir, '\', participant_name,'_site-',char(session_info(3)),'_mle_fc_cdt.png'])
        close all
        make_summary_plot_temp_recordings(PM)
        saveas(gcf,[block_dir, '\', participant_name,'_site-',char(session_info(3)),'_mle_fc_cdt_temp.png'])
        close all
    end  
    
    %% 2IFC warm detection 
    clear PM   
    clear params
    if run_wdt_2ifc
        [PM,params]=run_performance_2ifc_thresholding_task(TCS,'WDT',language,response_type,baseline,probe,stimulate,plot_stimulus);

        save([block_dir, '\', participant_name,'_site-',char(session_info(3)),'_mle_fc_wdt.mat'],'PM','params', '-v7.3')
        
        close all
        make_summary_plot_performance_2ifc(PM, params.n)
        saveas(gcf,[block_dir, '\', participant_name,'_site-',char(session_info(3)),'_mle_fc_wdt.png'])
        close all
        make_summary_plot_temp_recordings(PM)
        saveas(gcf,[block_dir, '\', participant_name,'_site-',char(session_info(3)),'_mle_fc_wdt_temp.png'])
        close all
    end  
end
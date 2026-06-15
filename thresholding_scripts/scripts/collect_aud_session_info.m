%Function used to collect participant/session information using a pop-up window. 
%Author: Arthur S. Courtin
%License: MIT

function answer = collect_aud_session_info()
    prompt = {'Participant code:','Status:','Site:','COM port:','Stimulate?:','Baseline temperature:'};
    dlgtitle = 'Input';
    fieldsize = [1 45; 1 45; 1 45; 1 45; 1 45; 1 45];
    definput = {'123','control(0) or patient(1)','LL(0) or UL(1)','3','no(0) or yes(1)','32'};
    answer = inputdlg(prompt,dlgtitle,fieldsize,definput);
end
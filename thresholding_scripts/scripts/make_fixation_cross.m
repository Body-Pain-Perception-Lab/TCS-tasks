%Function used to generate a fixation cross texture that can be plotted by
%Psychtoolbox.
%Author: Arthur S. Courtin
%License: MIT 

function fixcross=make_fixation_cross(expWin,background_color,text_color)

    for i=1:3
        FixCr(:,:,i)=ones(50,50)*background_color(i);
        FixCr(20:31,:,i)=text_color(i);
        FixCr(:,20:31,i)=text_color(i);
    end
    fixcross = Screen('MakeTexture',expWin,FixCr);
end
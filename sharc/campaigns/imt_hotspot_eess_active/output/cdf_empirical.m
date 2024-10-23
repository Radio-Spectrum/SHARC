function out = cdf_empirical(X)
% compute the Empirical Cumulative Distribution Function 
% (CDF) of the input array X in the current figure. The empirical 
% CDF y=F(x) is defined as the proportion of X values less than or equal to x.
% If input X is a matrix, then cdfplot(X) parses it to the vector and 
% displays CDF of all values.

tmp = sort(reshape(X,prod(size(X)),1));
%Xplot = reshape([tmp tmp].',2*length(tmp),1);
Xplot = tmp;

tmp = [1:length(X)].'/length(X);
%Yplot = reshape([tmp tmp].',2*length(tmp),1);
Yplot = tmp;
%Yplot = [Yplot(1:(end-1))];
out = [Xplot Yplot];  
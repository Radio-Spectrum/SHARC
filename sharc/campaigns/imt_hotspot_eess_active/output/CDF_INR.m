
%ind = randperm(numel(INR_DL_SM(:,1)));
%rdn_INR_DL_SM = INR_DL_SM(ind,1);


INR_DL_LG = INR_DL_LG(1:2400,2) + 10*log10(2047.6);
INR_UL_LG = INR_UL_LG(1:2400,2) + 10*log10(2047.6);
INR_DL_SM = INR_DL_SM(1:2400,2);
INR_UL_SM = INR_UL_SM(1:2400,2);

INR_DL_SM_lin = 10.^(INR_DL_SM/10);
INR_DL_LG_lin = 10.^(INR_DL_LG/10);
INR_UL_SM_lin = 10.^(INR_UL_SM/10);
INR_UL_LG_lin = 10.^(INR_UL_LG/10);

INR_DL = INR_DL_SM_lin  + INR_DL_LG_lin; 
INR_UL = INR_UL_SM_lin  + INR_UL_LG_lin;

Ind1 = round(rand(length(INR_DL),1)*(length(INR_DL)-1))+1; 
Ind2 = round(rand(length(INR_DL),1)*(length(INR_DL)-1))+1;
Ind3 = round(rand(length(INR_DL),1)*(length(INR_DL)-1))+1; 
Ind4 = round(rand(length(INR_DL),1)*(length(INR_DL)-1))+1;
Ind5 = round(rand(length(INR_DL),1)*(length(INR_DL)-1))+1; 
Ind6 = round(rand(length(INR_DL),1)*(length(INR_DL)-1))+1;

INR_Agg_1 = 10*log10(0.75*(INR_DL_SM_lin(Ind3)+INR_DL_LG_lin(Ind4)) + 0.25*(INR_UL_SM_lin(Ind5)+INR_UL_LG_lin(Ind6)));
INR_Agg_2 = 10*log10(0.75 * INR_DL(Ind1) + 0.25 * INR_UL(Ind2));

CDF_INR_DL_LG = cdf_empirical(INR_DL_LG);
CDF_INR_DL_SM = cdf_empirical(INR_DL_SM);
CDF_INR_UL_LG = cdf_empirical(INR_UL_LG);
CDF_INR_UL_SM = cdf_empirical(INR_UL_SM);
CDF_INR_Agg_1 = cdf_empirical(INR_Agg_1);
CDF_INR_Agg_2 = cdf_empirical(INR_Agg_2);


figure;

plot(CDF_INR_DL_LG(:,1),CDF_INR_DL_LG(:,2),'LineWidth',2)
hold on;
plot(CDF_INR_UL_LG(:,1),CDF_INR_UL_LG(:,2),'LineWidth',2)
plot(CDF_INR_DL_SM(:,1),CDF_INR_DL_SM(:,2),'LineWidth',2)
plot(CDF_INR_UL_SM(:,1),CDF_INR_UL_SM(:,2),'LineWidth',2)
plot(CDF_INR_Agg_1(:,1),CDF_INR_Agg_1(:,2),'LineWidth',2)
plot(CDF_INR_Agg_2(:,1),CDF_INR_Agg_2(:,2),'LineWidth',2)
legend('DL - large beam','UL - large beam','DL - 3dB spotbeam','UL - 3dB spotbeam','Aggregate CDF 1','Aggregate CDF 2')
xlabel('Interference to Noise Ratio [dB]')
ylabel('CDF [%]')
title('CDF of Interference to Noise Ratio for 18deg Nadir - EESS Active')
grid on
